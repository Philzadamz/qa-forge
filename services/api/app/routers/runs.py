"""Test Lab runs (PRD §7.6, §10). Web, API, and Android targets."""

import copy
import json
import threading
import uuid
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.enums import ExecutionMode, RunStatus, RunTarget, TestStatus
from app.core.rbac import require_project_access, require_user
from app.db.session import get_db
from app.models.apk import Apk
from app.models.project import Project
from app.models.test_case import TestCase
from app.models.test_run import RunStep, TestRun
from app.models.test_suite import TestSuite
from app.models.user import User
from app.schemas.runs import RunApplyIn, RunCreate, RunOut, RunStepOut
from app.services.execution.android_execution_runner import run_android_execution_job
from app.services.execution.api_execution_runner import run_api_execution_job
from app.services.execution.execution_runner import run_execution_job
from app.services.execution.run_events import RunEvent, request_cancel, subscribe, unsubscribe

router = APIRouter(tags=["runs"])


def _get_suite_or_404(db: Session, suite_id: uuid.UUID, user: User) -> tuple[TestSuite, Project]:
    suite = db.get(TestSuite, suite_id)
    if suite is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Suite not found")
    project = db.get(Project, suite.project_id)
    if project is None or project.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_access(project, user)
    return suite, project


def _get_run_or_404(db: Session, run_id: uuid.UUID, user: User) -> TestRun:
    run = db.get(TestRun, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Run not found")
    project = db.get(Project, run.project_id)
    if project is not None:
        require_project_access(project, user)
    return run


@router.get("/suites/{suite_id}/runs", response_model=list[RunOut])
def list_runs(
    suite_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[TestRun]:
    _get_suite_or_404(db, suite_id, user)
    return list(
        db.query(TestRun)
        .filter(TestRun.suite_id == suite_id)
        .order_by(TestRun.created_at.desc())
        .all()
    )


@router.post("/runs", response_model=RunOut, status_code=status.HTTP_201_CREATED)
def create_run(
    payload: RunCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TestRun:
    suite, project = _get_suite_or_404(db, payload.suite_id, user)
    cases = (
        db.query(TestCase)
        .filter(TestCase.suite_id == suite.id, TestCase.id.in_(payload.case_ids))
        .all()
    )
    found_ids = {c.id for c in cases}
    missing = set(payload.case_ids) - found_ids
    if missing:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Case(s) not found in this suite: {sorted(str(m) for m in missing)}",
        )

    config_json: dict[str, object] = {
        "force_agent": payload.force_agent,
        "self_heal": payload.self_heal,
    }

    if payload.target == RunTarget.ANDROID:
        if payload.apk_id is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, "apk_id is required for an Android run"
            )
        apk = db.get(Apk, payload.apk_id)
        if apk is None or apk.project_id != project.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "APK not found in this project")
        config_json["apk_id"] = str(apk.id)
    else:
        target_url = payload.target_url or project.default_test_url
        if not target_url:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No target URL given and the project has no default test URL configured",
            )
        config_json["target_url"] = target_url
        config_json["base_url"] = target_url
        if payload.target == RunTarget.API:
            missing_plan = [c.id for c in cases if not c.request_plan]
            if missing_plan:
                ids = sorted(str(m) for m in missing_plan)
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST, f"Case(s) have no compiled request plan: {ids}"
                )
        if payload.default_headers:
            config_json["default_headers"] = payload.default_headers
        if payload.env_vars:
            config_json["env_vars"] = payload.env_vars

    run = TestRun(
        suite_id=suite.id,
        project_id=project.id,
        target=payload.target,
        status=RunStatus.QUEUED,
        config_json=config_json,
        guidance_text=payload.guidance_text,
        selected_case_ids=[str(cid) for cid in payload.case_ids],
    )
    db.add(run)
    audit_record(
        db,
        actor_id=user.id,
        action="start_run",
        entity="test_run",
        entity_id=str(run.id),
        diff={"suite_id": str(suite.id), "case_count": len(payload.case_ids)},
        request=request,
    )
    db.commit()
    db.refresh(run)

    target_job = {
        RunTarget.API: run_api_execution_job,
        RunTarget.ANDROID: run_android_execution_job,
    }.get(payload.target, run_execution_job)
    thread = threading.Thread(target=target_job, args=(run.id,), daemon=True)
    thread.start()

    return run


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(
    run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> TestRun:
    return _get_run_or_404(db, run_id, user)


@router.get("/runs/{run_id}/steps", response_model=list[RunStepOut])
def get_run_steps(
    run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[RunStep]:
    _get_run_or_404(db, run_id, user)
    return list(db.query(RunStep).filter(RunStep.run_id == run_id).order_by(RunStep.seq).all())


@router.post("/runs/{run_id}/cancel", response_model=RunOut)
def cancel_run(
    run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> TestRun:
    run = _get_run_or_404(db, run_id, user)
    if run.status in (RunStatus.QUEUED, RunStatus.RUNNING):
        request_cancel(str(run_id))
    return run


@router.get("/runs/{run_id}/events")
def run_events_stream(
    run_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> StreamingResponse:
    run = _get_run_or_404(db, run_id, user)

    def event_stream() -> Iterator[str]:
        if run.status in (RunStatus.PASSED, RunStatus.FAILED, RunStatus.ERROR, RunStatus.CANCELLED):
            payload: RunEvent = {"type": "run_done", "status": run.status.value}
            if run.error:
                payload["error"] = run.error
            yield f"data: {json.dumps(dict(payload))}\n\n"
            return

        q = subscribe(str(run_id))
        try:
            while True:
                event: RunEvent = q.get(timeout=300)
                yield f"data: {json.dumps(dict(event))}\n\n"
                if event.get("type") == "run_done":
                    return
        except Exception:
            return
        finally:
            unsubscribe(str(run_id), q)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/runs/{run_id}/apply", response_model=RunOut)
def apply_run(
    run_id: uuid.UUID,
    payload: RunApplyIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> TestRun:
    run = _get_run_or_404(db, run_id, user)
    if run.status not in (RunStatus.PASSED, RunStatus.FAILED):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "Only a finished run's results can be applied"
        )
    # Deep copy: a shallow `dict(...)` would still share the nested per-case dicts with
    # `run.summary_json`'s current value, so mutating `result["applied"]` below would also
    # mutate the "old" value SQLAlchemy compares against for its dirty-check — the two would
    # end up `==` and the UPDATE would silently never be issued.
    cases_field = copy.deepcopy(run.summary_json.get("cases", {}))
    case_results: dict[str, dict[str, object]] = (
        cases_field if isinstance(cases_field, dict) else {}
    )
    target_ids = (
        {str(cid) for cid in payload.case_ids}
        if payload.case_ids is not None
        else set(case_results)
    )
    unknown = target_ids - set(case_results)
    if unknown:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, f"Not part of this run's results: {sorted(unknown)}"
        )

    applied = []
    for case_id_str in target_ids:
        result = case_results[case_id_str]
        case = db.get(TestCase, uuid.UUID(case_id_str))
        if case is None:
            continue
        case.status = TestStatus(str(result["status"]))
        case.actual_result = str(result["actual_result"])
        case.execution_mode = ExecutionMode.AUTOMATED
        case.last_run_id = run.id
        result["applied"] = True
        applied.append(case_id_str)

    run.summary_json = {**run.summary_json, "cases": case_results}
    audit_record(
        db,
        actor_id=user.id,
        action="apply_run",
        entity="test_run",
        entity_id=str(run.id),
        diff={"applied_case_ids": applied},
        request=request,
    )
    db.commit()
    db.refresh(run)
    return run
