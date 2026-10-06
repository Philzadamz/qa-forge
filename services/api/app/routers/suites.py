"""Test suites: create from a type's defaults, generate functional cases, track jobs."""

import json
import threading
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.config import get_settings
from app.core.enums import CaseSection, CaseSource, GenerationJobStatus, TestStatus
from app.core.features import ensure_feature
from app.core.rbac import require_project_access, require_user
from app.db.session import get_db
from app.models.generation_job import GenerationJob
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_case_type import DefaultTestCase, TestCaseType
from app.models.test_suite import TestSuite
from app.models.user import User
from app.models.user_story import UserStory
from app.schemas.suites import GenerateRequest, JobOut, SuiteCreate, SuiteOut, SuitePatch
from app.services.ai.analyze import PROMPT_VERSION as ANALYZE_PROMPT_VERSION
from app.services.suites.generation_runner import run_generation_job
from app.services.suites.job_events import JobEvent, subscribe, unsubscribe
from app.services.suites.numbering import renumber_suite_cases

router = APIRouter(tags=["suites"])


def _get_project_or_404(db: Session, project_id: uuid.UUID, user: User) -> Project:
    obj = db.get(Project, project_id)
    if obj is None or obj.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_access(obj, user)
    return obj


def _get_suite_or_404(db: Session, suite_id: uuid.UUID, user: User) -> tuple[TestSuite, Project]:
    suite = db.get(TestSuite, suite_id)
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suite not found")
    project = _get_project_or_404(db, suite.project_id, user)
    return suite, project


def _snapshot_and_create_default_cases(db: Session, suite: TestSuite, type_id: uuid.UUID) -> None:
    """(Re)creates the suite's DEFAULT-section cases from the type's currently-active
    defaults, snapshotting them onto the suite (ADM-DC-6) so later admin edits don't
    silently change an in-progress suite."""
    db.query(TestCase).filter(
        TestCase.suite_id == suite.id, TestCase.section == CaseSection.DEFAULT
    ).delete()

    defaults = (
        db.query(DefaultTestCase)
        .filter(DefaultTestCase.type_id == type_id, DefaultTestCase.is_active.is_(True))
        .order_by(DefaultTestCase.sort_order)
        .all()
    )
    snapshot = []
    for i, default in enumerate(defaults):
        db.add(
            TestCase(
                suite_id=suite.id,
                section=CaseSection.DEFAULT,
                case_no=0,
                display_id="",
                feature=default.feature,
                scenario=default.scenario,
                steps=list(default.steps),
                expected_result=default.expected_result,
                actual_result="",
                status=TestStatus.NOT_TESTED,
                evidence_group=default.evidence_group,
                tags=list(default.tags),
                source=CaseSource.DEFAULT,
                default_case_id=default.id,
                included=True,
                sort_order=i,
            )
        )
        snapshot.append(
            {
                "id": str(default.id),
                "version": default.version,
                "feature": default.feature,
                "scenario": default.scenario,
            }
        )
    suite.default_version_snapshot = {"type_id": str(type_id), "defaults": snapshot}
    # This session has autoflush=False (app/db/session.py) — renumber_suite_cases queries
    # TestCase right after this, so the rows just added here need to be visible to it.
    db.flush()


@router.get("/projects/{project_id}/suites", response_model=list[SuiteOut])
def list_suites(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[TestSuite]:
    _get_project_or_404(db, project_id, user)
    return list(
        db.query(TestSuite)
        .filter(TestSuite.project_id == project_id)
        .order_by(TestSuite.created_at.desc())
        .all()
    )


@router.post("/suites", response_model=SuiteOut, status_code=status.HTTP_201_CREATED)
def create_suite(
    payload: SuiteCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TestSuite:
    project = _get_project_or_404(db, payload.project_id, user)
    type_obj = db.get(TestCaseType, payload.type_id)
    if type_obj is None or not type_obj.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Test case type not found or inactive")

    suite = TestSuite(
        project_id=payload.project_id,
        type_id=payload.type_id,
        name=payload.name,
        story_ids=[str(s) for s in payload.story_ids],
        header_json=payload.header.model_dump(),
    )
    db.add(suite)
    db.flush()

    _snapshot_and_create_default_cases(db, suite, payload.type_id)
    renumber_suite_cases(db, suite.id, project.id_prefix)

    audit_record(
        db,
        actor_id=user.id,
        action="create",
        entity="test_suite",
        entity_id=str(suite.id),
        request=request,
    )
    db.commit()
    db.refresh(suite)
    return suite


@router.get("/suites/{suite_id}", response_model=SuiteOut)
def get_suite(
    suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> TestSuite:
    suite, _ = _get_suite_or_404(db, suite_id, user)
    return suite


@router.patch("/suites/{suite_id}", response_model=SuiteOut)
def update_suite(
    suite_id: uuid.UUID,
    payload: SuitePatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TestSuite:
    suite, _ = _get_suite_or_404(db, suite_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if "story_ids" in changes:
        changes["story_ids"] = [str(s) for s in changes["story_ids"]]
    if "header" in changes:
        suite.header_json = changes.pop("header")
    for key, value in changes.items():
        setattr(suite, key, value)
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="test_suite",
        entity_id=str(suite.id),
        diff=changes,
        request=request,
    )
    db.commit()
    db.refresh(suite)
    return suite


@router.post("/suites/{suite_id}/refresh-defaults", response_model=SuiteOut)
def refresh_defaults(
    suite_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TestSuite:
    suite, project = _get_suite_or_404(db, suite_id, user)
    _snapshot_and_create_default_cases(db, suite, suite.type_id)
    renumber_suite_cases(db, suite.id, project.id_prefix)
    audit_record(
        db,
        actor_id=user.id,
        action="refresh_defaults",
        entity="test_suite",
        entity_id=str(suite.id),
        request=request,
    )
    db.commit()
    db.refresh(suite)
    return suite


@router.post(
    "/suites/{suite_id}/generate", response_model=JobOut, status_code=status.HTTP_201_CREATED
)
def start_generation(
    suite_id: uuid.UUID,
    payload: GenerateRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> GenerationJob:
    ensure_feature(db, "ai_case_generation")
    suite, _ = _get_suite_or_404(db, suite_id, user)
    story_ids = payload.story_ids or [uuid.UUID(s) for s in suite.story_ids]
    if not story_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No stories selected for this suite")
    stories = db.query(UserStory).filter(UserStory.id.in_(story_ids)).all()
    if len(stories) != len(story_ids):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "One or more stories were not found")

    job = GenerationJob(
        suite_id=suite.id,
        story_ids=[str(s) for s in story_ids],
        status=GenerationJobStatus.QUEUED,
        model=get_settings().ai_model_generation,
        prompt_version=ANALYZE_PROMPT_VERSION,
    )
    db.add(job)
    audit_record(
        db,
        actor_id=user.id,
        action="generate",
        entity="test_suite",
        entity_id=str(suite.id),
        request=request,
    )
    db.commit()
    db.refresh(job)

    thread = threading.Thread(target=run_generation_job, args=(job.id,), daemon=True)
    thread.start()

    return job


@router.get("/jobs/{job_id}", response_model=JobOut)
def get_job(
    job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    _get_suite_or_404(db, job.suite_id, user)
    return job


@router.get("/jobs/{job_id}/events")
def job_events(
    job_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> StreamingResponse:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    _get_suite_or_404(db, job.suite_id, user)

    def event_stream() -> Iterator[str]:
        if job.status in (GenerationJobStatus.SUCCEEDED, GenerationJobStatus.FAILED):
            # The job can finish before the client even connects (a FakeLLM failure is
            # near-instant) — this replay must carry the same fields a live job_done event
            # would, or the client loses the error message.
            payload: JobEvent = {"type": "job_done", "status": job.status.value}
            if job.error:
                payload["error"] = job.error
            yield f"data: {json.dumps(dict(payload))}\n\n"
            return

        q = subscribe(str(job_id))
        try:
            while True:
                event: JobEvent = q.get(timeout=300)
                yield f"data: {json.dumps(dict(event))}\n\n"
                if event.get("type") == "job_done":
                    return
        except Exception:
            return
        finally:
            unsubscribe(str(job_id), q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/suites/{suite_id}/cycles", response_model=SuiteOut)
def start_new_cycle(
    suite_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TestSuite:
    """Resets every case's status/actual result to Not Tested, keeping history via the bumped
    `test_cycle` counter (used later in the report's "Test Cycles" figure, PRD §3.2(d))."""
    suite, _ = _get_suite_or_404(db, suite_id, user)
    cases = db.query(TestCase).filter(TestCase.suite_id == suite.id).all()
    for case in cases:
        case.status = TestStatus.NOT_TESTED
        case.actual_result = ""
    suite.test_cycle += 1
    audit_record(
        db,
        actor_id=user.id,
        action="new_cycle",
        entity="test_suite",
        entity_id=str(suite.id),
        request=request,
    )
    db.commit()
    db.refresh(suite)
    return suite
