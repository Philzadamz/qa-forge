"""Runs one generation job end to end in a background thread (PRD §8.2, §10).

Started via `threading.Thread` from the `POST /suites/{id}/generate` handler and given only
the job's id — it opens its own DB session rather than sharing the request's (which closes
as soon as the response is sent). Progress is published via `job_events` for the SSE
endpoint to relay; final state always lands in the `generation_jobs` row so a client that
reconnects mid-run (or after it finished) can still read the outcome.
"""

import logging
import uuid

from app.core.config import get_settings
from app.core.enums import CaseSection, CaseSource, GenerationJobStatus, Priority, TestStatus
from app.db.base import utcnow
from app.db.session import get_sessionmaker
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_suite import TestSuite
from app.models.user_story import UserStory
from app.services.ai.analyze import PROMPT_VERSION as ANALYZE_PROMPT_VERSION
from app.services.ai.analyze import analyze_story
from app.services.ai.client import build_llm_client
from app.services.ai.masking import mask_text
from app.services.ai.orchestrator import GenerationConfig, run_generation
from app.services.ai.schemas import FunctionalCase
from app.services.suites.job_events import publish
from app.services.suites.numbering import renumber_suite_cases

logger = logging.getLogger(__name__)


def _case_from_functional(
    suite_id: uuid.UUID, case: FunctionalCase, sort_order: int, *, is_duplicate: bool
) -> TestCase:
    return TestCase(
        suite_id=suite_id,
        section=CaseSection.FUNCTIONAL,
        case_no=0,
        display_id="",
        feature=case.feature,
        scenario=case.scenario,
        steps=case.steps,
        expected_result=case.expected_result,
        actual_result="",
        status=TestStatus.NOT_TESTED,
        evidence_group=case.evidence_group or case.feature,
        priority=Priority(case.priority),
        technique=list(case.techniques),
        traces_to=list(case.traces_to),
        source=CaseSource.AI,
        included=not is_duplicate,
        is_duplicate=is_duplicate,
        sort_order=sort_order,
    )


def run_generation_job(job_id: uuid.UUID) -> None:
    session = get_sessionmaker()()
    job = session.get(GenerationJob, job_id)
    if job is None:
        session.close()
        return

    try:
        job.status = GenerationJobStatus.RUNNING
        job.started_at = utcnow()
        session.commit()

        suite = session.get(TestSuite, job.suite_id)
        if suite is None:
            raise RuntimeError("Suite no longer exists")
        project = session.get(Project, suite.project_id)
        if project is None:
            raise RuntimeError("Project no longer exists")

        story_uuids = [uuid.UUID(s) for s in job.story_ids]
        stories = session.query(UserStory).filter(UserStory.id.in_(story_uuids)).all()
        if not stories:
            raise RuntimeError("No stories selected for generation")

        settings = get_settings()
        client = build_llm_client(settings)

        combined_text = "\n\n---\n\n".join(s.extracted_text for s in stories)
        masked = mask_text(combined_text)
        if masked.total_masked:
            logger.info(
                "Masked %s PII item(s) before sending story to the model", masked.total_masked
            )

        analysis = analyze_story(client, story_text=masked.text, model=settings.ai_model_generation)
        stories[0].analysis_json = analysis.model_dump(mode="json")
        stories[0].acceptance_criteria = [
            ac.model_dump(mode="json") for ac in analysis.acceptance_criteria
        ]
        session.commit()

        default_summaries = [
            c.scenario
            for c in session.query(TestCase)
            .filter(TestCase.suite_id == suite.id, TestCase.section == CaseSection.DEFAULT)
            .all()
        ]

        config = GenerationConfig(model_generation=settings.ai_model_generation)
        sort_order_counter = session.query(TestCase).filter(TestCase.suite_id == suite.id).count()

        def on_feature_done(feature: str, cases: list[FunctionalCase]) -> None:
            nonlocal sort_order_counter
            for case in cases:
                row = _case_from_functional(suite.id, case, sort_order_counter, is_duplicate=False)
                session.add(row)
                sort_order_counter += 1
            session.commit()
            publish(
                str(job_id), {"type": "feature_done", "feature": feature, "case_count": len(cases)}
            )

        outcome = run_generation(
            client,
            analysis=analysis,
            config=config,
            default_scenario_summaries=default_summaries,
            on_feature_done=on_feature_done,
        )

        # Mark duplicates found across the *whole* set (on_feature_done persisted rows before
        # cross-feature dedup could see them) — flag by matching scenario text.
        if outcome.duplicate_indexes:
            duplicate_scenarios = {outcome.cases[i].scenario for i in outcome.duplicate_indexes}
            rows = (
                session.query(TestCase)
                .filter(TestCase.suite_id == suite.id, TestCase.source == CaseSource.AI)
                .all()
            )
            for row in rows:
                if row.scenario in duplicate_scenarios:
                    row.is_duplicate = True
                    row.included = False
            session.commit()

        renumber_suite_cases(session, suite.id, project.id_prefix)
        session.commit()

        job.status = GenerationJobStatus.SUCCEEDED
        job.finished_at = utcnow()
        job.prompt_version = ANALYZE_PROMPT_VERSION
        session.commit()
        publish(str(job_id), {"type": "job_done", "status": "succeeded"})
    except Exception as exc:
        logger.exception("Generation job %s failed", job_id)
        job.status = GenerationJobStatus.FAILED
        job.error = str(exc)[:2000]
        job.finished_at = utcnow()
        session.commit()
        publish(str(job_id), {"type": "job_done", "status": "failed", "error": str(exc)[:500]})
    finally:
        session.close()
