"""Runs one API-target Test Lab run end to end (PRD §7.6.2), mirroring
`execution_runner.py`'s Web counterpart: own DB session, SSE progress via `run_events`,
review-before-apply (verdicts land in `TestRun.summary_json` only; `POST /runs/{id}/apply`
writes them into the suite — see `execution_runner.py`'s docstring for the full rationale).

No browser, no agent loop: once a case has a `request_plan`, running it is deterministic
httpx, so this is simpler than the Web runner. One `httpx.Client` and one variable-chaining
`context` dict are shared across every selected case in the run, in order, so a later case can
reference an earlier one's `extract`ed values (PRD: "chained flows ... via extracted
variables") — chaining happens *across* cases in a run, not just within one case.
"""

import logging
import uuid

import httpx

from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.core.enums import RunStatus, RunStepOutcome, TestStatus
from app.core.metrics import RUN_DURATION, run_duration_seconds
from app.db.base import utcnow
from app.db.session import get_sessionmaker
from app.models.evidence import Evidence
from app.models.project import Project
from app.models.secret import Secret
from app.models.test_case import TestCase
from app.models.test_run import RunStep, TestRun
from app.services.execution.api_models import RequestPlan
from app.services.execution.api_runner import execute_request_plan
from app.services.execution.run_events import clear_cancel, is_cancelled, publish
from app.services.storage import build_storage

logger = logging.getLogger(__name__)


def _check_allowlist(base_url: str, project: Project) -> None:
    allowed_prefixes = [p for p in (project.default_test_url,) if p]
    allowed_prefixes += ["http://127.0.0.1", "http://localhost"]
    if not any(base_url.startswith(p) for p in allowed_prefixes):
        raise RuntimeError(
            f"Base URL {base_url!r} is not allowlisted for this project "
            "(must match the project's default test URL, or be a local target)"
        )


def run_api_execution_job(run_id: uuid.UUID) -> None:
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

        base_url = str(run.config_json.get("base_url") or project.default_test_url or "")
        if not base_url:
            raise RuntimeError("No base URL configured for this run")
        _check_allowlist(base_url, project)

        case_ids = [uuid.UUID(c) for c in run.selected_case_ids]
        cases_by_id = {
            c.id: c for c in session.query(TestCase).filter(TestCase.id.in_(case_ids)).all()
        }
        ordered_cases = [cases_by_id[cid] for cid in case_ids if cid in cases_by_id]
        if not ordered_cases:
            raise RuntimeError("No valid cases selected for this run")

        settings = get_settings()
        storage = build_storage(settings)

        secrets = session.query(Secret).filter(Secret.project_id == project.id).all()
        secret_values = [decrypt_secret(s.ciphertext, settings) for s in secrets]
        context: dict[str, str] = {
            f"secret_{s.name}": decrypt_secret(s.ciphertext, settings) for s in secrets
        }
        env_vars = run.config_json.get("env_vars")
        if isinstance(env_vars, dict):
            context.update({str(k): str(v) for k, v in env_vars.items()})
        default_headers_raw = run.config_json.get("default_headers")
        default_headers: dict[str, str] = (
            {str(k): str(v) for k, v in default_headers_raw.items()}
            if isinstance(default_headers_raw, dict)
            else {}
        )

        results: dict[str, dict[str, object]] = {}
        counts = {"passed": 0, "failed": 0, "blocked": 0}
        cancelled = False

        with httpx.Client() as client:
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

                if not case.request_plan:
                    status = TestStatus.BLOCKED
                    actual_result = "This case has no compiled request plan."
                else:
                    plan = RequestPlan.model_validate(case.request_plan)
                    merged_headers = {**default_headers, **plan.headers}
                    plan = plan.model_copy(update={"headers": merged_headers})
                    step_result = execute_request_plan(
                        plan,
                        base_url=base_url,
                        client=client,
                        context=context,
                        secret_values=secret_values,
                    )
                    context.update(step_result.extracted)
                    status = step_result.status
                    actual_result = step_result.actual_result

                    png_id = uuid.uuid4()
                    png_key = f"evidence/{case.suite_id}/{case.id}/{png_id}.png"
                    storage.put(png_key, step_result.log_image)
                    session.add(
                        Evidence(
                            id=png_id,
                            test_case_id=case.id,
                            run_id=run.id,
                            file_key=png_key,
                            caption=f"{plan.method} {plan.path} — {actual_result[:150]}",
                        )
                    )
                    txt_id = uuid.uuid4()
                    txt_key = f"evidence/{case.suite_id}/{case.id}/{txt_id}.txt"
                    storage.put(txt_key, step_result.log_text.encode("utf-8"))
                    session.add(
                        Evidence(
                            id=txt_id,
                            test_case_id=case.id,
                            run_id=run.id,
                            file_key=txt_key,
                            caption="Masked request/response log (text)",
                        )
                    )
                    session.add(
                        RunStep(
                            run_id=run.id,
                            test_case_id=case.id,
                            seq=1,
                            action=f"{plan.method} {plan.path}",
                            target=base_url,
                            input_masked=None,
                            assertion=None,
                            outcome=RunStepOutcome.PASS
                            if status == TestStatus.PASSED
                            else RunStepOutcome.FAIL,
                            message=actual_result[:2000],
                            screenshot_evidence_id=png_id,
                            duration_ms=step_result.duration_ms,
                        )
                    )
                    session.commit()

                results[str(case.id)] = {
                    "status": status.value,
                    "actual_result": actual_result,
                    "confidence": 1.0,
                    "mode": "api",
                    "applied": False,
                }
                if status == TestStatus.PASSED:
                    counts["passed"] += 1
                elif status == TestStatus.FAILED:
                    counts["failed"] += 1
                else:
                    counts["blocked"] += 1
                publish(
                    str(run_id),
                    {"type": "case_done", "case_id": str(case.id), "status": status.value},
                )

        if cancelled:
            run.status = RunStatus.CANCELLED
        elif counts["failed"] == 0 and counts["blocked"] == 0:
            run.status = RunStatus.PASSED
        else:
            run.status = RunStatus.FAILED
        run.finished_at = utcnow()
        RUN_DURATION.labels(target="api", status=run.status.value).observe(
            run_duration_seconds(run.started_at, run.finished_at)
        )
        run.summary_json = {"total": len(ordered_cases), **counts, "cases": results}
        session.commit()
        publish(str(run_id), {"type": "run_done", "status": run.status.value})
    except Exception as exc:
        logger.exception("API run %s failed", run_id)
        run.status = RunStatus.ERROR
        run.error = str(exc)[:2000]
        run.finished_at = utcnow()
        RUN_DURATION.labels(target="api", status="error").observe(
            run_duration_seconds(run.started_at, run.finished_at)
        )
        session.commit()
        publish(str(run_id), {"type": "run_done", "status": "error", "error": str(exc)[:500]})
    finally:
        clear_cancel(str(run_id))
        session.close()
