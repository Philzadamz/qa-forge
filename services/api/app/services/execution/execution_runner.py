"""Runs one Test Lab run end to end in a background thread (PRD §7.6, §10), mirroring
`suites/generation_runner.py`'s split: opens its own DB session, publishes progress via
`run_events` for the SSE endpoint, and always leaves a final state on the `test_runs` row so a
client that reconnects mid-run (or after it finished) can still read the outcome.

**Review-before-apply (PRD §7.6, §15 risk table — "AI marks a failing test as passed"):**
per-case verdicts (status/actual_result) are written only to `TestRun.summary_json`, never to
the `TestCase` row, during the run itself — `POST /runs/{id}/apply` is what writes them into
the suite. Evidence screenshots ARE attached to the case as they're captured (needed for the
live run view's "latest screenshot", and for the per-step audit trail) — the PRD's apply-time
risk concern is specifically about silently overwriting a case's pass/fail verdict, not about
evidence images, so this scope cut only gates the verdict. One effect of that choice: evidence
from a run that's never applied stays attached to the case (visible in exports) unless deleted
by hand — a known limitation, not a silent gap (see docs/progress.md).
"""

import contextlib
import logging
import uuid
from collections.abc import Callable

from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.core.crypto import decrypt_secret
from app.core.enums import CaseSection, RunStatus, RunStepOutcome, TestStatus
from app.db.base import utcnow
from app.db.session import get_sessionmaker
from app.models.evidence import Evidence
from app.models.project import Project
from app.models.secret import Secret
from app.models.test_case import TestCase
from app.models.test_run import RunStep, TestRun
from app.services.execution.agent import CaseRunResult, CaseStepEvent, run_case_with_agent
from app.services.execution.agent_client import AgentClientError, build_agent_client
from app.services.execution.deterministic import routine_for_tags
from app.services.execution.run_events import clear_cancel, is_cancelled, publish
from app.services.execution.script_mode import build_script, replay_script
from app.services.execution.tools import BrowserTools
from app.services.storage import Storage, build_storage

logger = logging.getLogger(__name__)


def _check_allowlist(target_url: str, project: Project) -> None:
    allowed_prefixes = [p for p in (project.default_test_url,) if p]
    allowed_prefixes += ["http://127.0.0.1", "http://localhost"]
    if not any(target_url.startswith(p) for p in allowed_prefixes):
        raise RuntimeError(
            f"Target URL {target_url!r} is not allowlisted for this project "
            "(must match the project's default test URL, or be a local target)"
        )


def run_execution_job(run_id: uuid.UUID) -> None:
    session = get_sessionmaker()()
    run = session.get(TestRun, run_id)
    if run is None:
        session.close()
        return

    try:
        run.status = RunStatus.RUNNING
        run.started_at = utcnow()
        session.commit()

        project = session.get(Project, run.project_id)
        if project is None:
            raise RuntimeError("Project no longer exists")

        target_url = str(run.config_json.get("target_url") or project.default_test_url or "")
        if not target_url:
            raise RuntimeError("No target URL configured for this run")
        _check_allowlist(target_url, project)

        case_ids = [uuid.UUID(c) for c in run.selected_case_ids]
        cases_by_id = {
            c.id: c for c in session.query(TestCase).filter(TestCase.id.in_(case_ids)).all()
        }
        ordered_cases = [cases_by_id[cid] for cid in case_ids if cid in cases_by_id]
        if not ordered_cases:
            raise RuntimeError("No valid cases selected for this run")

        settings = get_settings()
        storage = build_storage(settings)

        def resolve_secret(name: str) -> str:
            secret = (
                session.query(Secret)
                .filter(Secret.project_id == project.id, Secret.name == name)
                .first()
            )
            if secret is None:
                raise KeyError(name)
            return decrypt_secret(secret.ciphertext, settings)

        results: dict[str, dict[str, object]] = {}
        counts = {"passed": 0, "failed": 0, "blocked": 0}

        from playwright.sync_api import sync_playwright

        cancelled = False
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                for case in ordered_cases:
                    if is_cancelled(str(run_id)):
                        cancelled = True
                        break
                    publish(
                        str(run_id),
                        {
                            "type": "case_started",
                            "case_id": str(case.id),
                            "display_id": case.display_id,
                        },
                    )
                    context = browser.new_context()
                    page = context.new_page()
                    tools = BrowserTools(page, allowed_url_prefix=target_url)

                    on_step = _make_step_persister(session, storage, run_id=run.id, case=case)

                    case_result, mode_used = _run_one_case(
                        case=case,
                        tools=tools,
                        target_url=target_url,
                        resolve_secret=resolve_secret,
                        settings=settings,
                        force_agent=bool(run.config_json.get("force_agent")),
                        allow_self_heal=bool(run.config_json.get("self_heal", True)),
                        on_step=on_step,
                    )
                    context.close()

                    if mode_used == "agent":
                        script = build_script(case_result)
                        if script is not None:
                            case.automation_script = script
                            session.commit()

                    results[str(case.id)] = {
                        "status": case_result.status.value,
                        "actual_result": case_result.actual_result,
                        "confidence": case_result.confidence,
                        "mode": mode_used,
                        "applied": False,
                    }
                    if case_result.status == TestStatus.PASSED:
                        counts["passed"] += 1
                    elif case_result.status == TestStatus.FAILED:
                        counts["failed"] += 1
                    else:
                        counts["blocked"] += 1

                    publish(
                        str(run_id),
                        {
                            "type": "case_done",
                            "case_id": str(case.id),
                            "status": case_result.status.value,
                        },
                    )
            finally:
                browser.close()

        if cancelled:
            run.status = RunStatus.CANCELLED
        elif counts["failed"] == 0 and counts["blocked"] == 0:
            run.status = RunStatus.PASSED
        else:
            run.status = RunStatus.FAILED
        run.finished_at = utcnow()
        run.summary_json = {"total": len(ordered_cases), **counts, "cases": results}
        session.commit()
        publish(str(run_id), {"type": "run_done", "status": run.status.value})
    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        run.status = RunStatus.ERROR
        run.error = str(exc)[:2000]
        run.finished_at = utcnow()
        session.commit()
        publish(str(run_id), {"type": "run_done", "status": "error", "error": str(exc)[:500]})
    finally:
        clear_cancel(str(run_id))
        session.close()


def _run_one_case(
    *,
    case: TestCase,
    tools: BrowserTools,
    target_url: str,
    resolve_secret: Callable[[str], str],
    settings: Settings,
    force_agent: bool,
    allow_self_heal: bool,
    on_step: Callable[[CaseStepEvent], None],
) -> tuple[CaseRunResult, str]:
    if case.automation_script and not force_agent:
        replay = replay_script(case.automation_script, tools=tools, resolve_secret=resolve_secret)
        for event in replay.steps:
            on_step(event)
        if replay.status == TestStatus.PASSED or not allow_self_heal:
            return (
                CaseRunResult(
                    status=replay.status, actual_result=replay.actual_result, confidence=1.0
                ),
                "script",
            )
        # self-heal: the stored script no longer works — fall through to agent mode.

    if case.section == CaseSection.DEFAULT:
        routine = routine_for_tags(case.tags)
        if routine is not None:
            result = routine(tools, target_url, resolve_secret)
            seq = 0
            for seq, line in enumerate(result.log, start=1):
                on_step(
                    CaseStepEvent(
                        seq=seq,
                        action="deterministic",
                        target=None,
                        input_masked=None,
                        assertion=None,
                        outcome=RunStepOutcome.PASS,
                        message=line,
                        screenshot=None,
                        duration_ms=0,
                    )
                )
            # One final screenshot of the end state, same as agent/script mode's `finish` step
            # — without this, a case executed purely by a deterministic routine would have no
            # evidence at all for the xlsx evidence sheet (PRD §7.6.1 "evidence in xlsx").
            final_screenshot = None
            with contextlib.suppress(Exception):
                final_screenshot = tools.screenshot()
            on_step(
                CaseStepEvent(
                    seq=seq + 1,
                    action="finish",
                    target=None,
                    input_masked=None,
                    assertion=None,
                    outcome=RunStepOutcome.PASS
                    if result.status == TestStatus.PASSED
                    else RunStepOutcome.FAIL,
                    message=result.actual_result,
                    screenshot=final_screenshot,
                    duration_ms=0,
                )
            )
            return (
                CaseRunResult(
                    status=result.status, actual_result=result.actual_result, confidence=1.0
                ),
                "deterministic",
            )

    client = build_agent_client(settings)
    try:
        case_result = run_case_with_agent(
            client,
            tools=tools,
            feature=case.feature,
            scenario=case.scenario,
            steps=list(case.steps),
            expected_result=case.expected_result,
            target_url=target_url,
            resolve_secret=resolve_secret,
            model=settings.ai_model_generation,
            on_step=on_step,
        )
    except AgentClientError as exc:
        case_result = CaseRunResult(
            status=TestStatus.BLOCKED, actual_result=f"Agent error: {exc}", confidence=0.0
        )
    return case_result, "agent"


def _make_step_persister(
    session: Session, storage: Storage, *, run_id: uuid.UUID, case: TestCase
) -> Callable[[CaseStepEvent], None]:
    def on_step(event: CaseStepEvent) -> None:
        evidence_id = None
        if event.screenshot is not None:
            evidence_id = uuid.uuid4()
            key = f"evidence/{case.suite_id}/{case.id}/{evidence_id}.png"
            storage.put(key, event.screenshot)
            session.add(
                Evidence(
                    id=evidence_id,
                    test_case_id=case.id,
                    run_id=run_id,
                    file_key=key,
                    caption=f"{event.action}: {event.message[:200]}",
                )
            )
        session.add(
            RunStep(
                run_id=run_id,
                test_case_id=case.id,
                seq=event.seq,
                action=event.action,
                target=event.target,
                input_masked=event.input_masked,
                assertion=event.assertion,
                outcome=event.outcome,
                message=event.message[:2000] if event.message else None,
                screenshot_evidence_id=evidence_id,
                duration_ms=event.duration_ms,
            )
        )
        session.commit()
        publish(
            str(run_id),
            {
                "type": "step",
                "case_id": str(case.id),
                "seq": event.seq,
                "action": event.action,
                "outcome": event.outcome.value,
                "message": event.message[:300] if event.message else "",
                "has_screenshot": evidence_id is not None,
            },
        )

    return on_step
