"""Runs one Android-target Test Lab run end to end (PRD §7.6.3), mirroring the Web/API
runners: own DB session, SSE progress via `run_events`, review-before-apply.

Per case: force-stop + fresh-launch the app (PRD §8.4 "fresh app relaunch per case"), clear
logcat, drive the agent loop, then check logcat for a crash/ANR referencing the app's package
and auto-fail the case if one is found — regardless of what the agent itself concluded, since
a crash is ground truth the agent may not even be able to observe (PRD §7.6.3: "auto-fail the
case on crash"). The APK is installed once at the start of the run and uninstalled at the end,
not per case — reinstalling a multi-MB APK before every case would make even a small run slow
for no isolation benefit the app relaunch doesn't already give.
"""

import logging
import re
import subprocess
import tempfile
import uuid
from collections.abc import Callable
from pathlib import Path

from sqlalchemy.orm import Session

from app.core import usage
from app.core.config import get_settings
from app.core.crypto import decrypt_secret
from app.core.enums import RunStatus, RunStepOutcome, TestStatus
from app.core.metrics import RUN_DURATION, run_duration_seconds
from app.db.base import utcnow
from app.db.session import get_sessionmaker
from app.models.apk import Apk
from app.models.evidence import Evidence
from app.models.project import Project
from app.models.secret import Secret
from app.models.test_case import TestCase
from app.models.test_run import RunStep, TestRun
from app.models.usage_record import UsageRecord
from app.services.execution.agent import CaseRunResult, CaseStepEvent
from app.services.execution.agent_client import AgentClientError, build_agent_client
from app.services.execution.android_agent import run_case_with_android_agent
from app.services.execution.android_provider import (
    AndroidDevice,
    LocalEmulatorProvider,
)
from app.services.execution.android_tools import AndroidTools
from app.services.execution.run_events import clear_cancel, is_cancelled, publish
from app.services.storage import Storage, build_storage

logger = logging.getLogger(__name__)

_CRASH_RE = re.compile(r"FATAL EXCEPTION|ANR in")


def _adb(adb_path: str, *args: str, timeout: float = 30.0) -> str:
    # adb_path is an admin-configured setting; args are our own fixed strings plus a device
    # serial/package name read from our own DB rows, never raw request input.
    result = subprocess.run(  # noqa: S603
        [adb_path, *args], capture_output=True, text=True, timeout=timeout
    )
    return result.stdout + result.stderr


def _check_for_crash(adb_path: str, udid: str, package_name: str) -> str | None:
    # A real crash's `FATAL EXCEPTION: main` line never carries the package name itself —
    # that's on the next line (`Process: <package>, PID: <n>`), e.g.:
    #   E AndroidRuntime: FATAL EXCEPTION: main
    #   E AndroidRuntime: Process: io.appium.android.apis, PID: 11317
    # so matching the crash marker and the package name on the *same* line (as an earlier
    # version of this check did) never fires on a real crash — this looks in a small window
    # of lines after the marker instead.
    output = _adb(adb_path, "-s", udid, "logcat", "-d")
    lines = output.splitlines()
    for idx, line in enumerate(lines):
        if not _CRASH_RE.search(line):
            continue
        window = lines[idx : idx + 5]
        if any(package_name in w for w in window):
            return "\n".join(lines[max(0, idx - 2) : idx + 15])
    return None


def run_android_execution_job(run_id: uuid.UUID) -> None:
    session = get_sessionmaker()()
    run = session.get(TestRun, run_id)
    if run is None:
        session.close()
        return

    device: AndroidDevice | None = None
    settings = get_settings()
    package_name: str | None = None

    try:
        run.status = RunStatus.RUNNING
        run.started_at = utcnow()
        session.commit()

        project = session.get(Project, run.project_id)
        if project is None:
            raise RuntimeError("Project no longer exists")

        apk_id = run.config_json.get("apk_id")
        if not apk_id:
            raise RuntimeError("No APK configured for this run")
        apk = session.get(Apk, uuid.UUID(str(apk_id)))
        if apk is None:
            raise RuntimeError("The configured APK no longer exists")
        package_name = apk.package_name

        case_ids = [uuid.UUID(c) for c in run.selected_case_ids]
        cases_by_id = {
            c.id: c for c in session.query(TestCase).filter(TestCase.id.in_(case_ids)).all()
        }
        ordered_cases = [cases_by_id[cid] for cid in case_ids if cid in cases_by_id]
        if not ordered_cases:
            raise RuntimeError("No valid cases selected for this run")

        storage = build_storage(settings)
        secrets = session.query(Secret).filter(Secret.project_id == project.id).all()
        secret_map = {s.name: decrypt_secret(s.ciphertext, settings) for s in secrets}

        def resolve_secret(name: str) -> str:
            if name not in secret_map:
                raise KeyError(name)
            return secret_map[name]

        provider = LocalEmulatorProvider(
            avd_name=settings.android_avd_name,
            appium_server_url=settings.android_appium_url,
            adb_path=settings.android_adb_path,
            emulator_path=settings.android_emulator_path,
            boot_timeout_seconds=settings.android_boot_timeout_seconds,
        )
        device = provider.acquire_device()
        adb_path = settings.android_adb_path

        with tempfile.TemporaryDirectory() as tmp_dir:
            apk_path = Path(tmp_dir) / "app.apk"
            apk_path.write_bytes(storage.get(apk.file_key))
            install_output = _adb(
                adb_path, "-s", device.udid, "install", "-r", "-g", str(apk_path), timeout=120
            )
            if "Success" not in install_output:
                raise RuntimeError(f"Could not install the APK: {install_output.strip()[:500]}")

        results: dict[str, dict[str, object]] = {}
        counts = {"passed": 0, "failed": 0, "blocked": 0}
        cancelled = False

        from appium import webdriver
        from appium.options.android import UiAutomator2Options

        with usage.track() as sink:
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

                _adb(adb_path, "-s", device.udid, "shell", "am", "force-stop", apk.package_name)
                _adb(adb_path, "-s", device.udid, "logcat", "-c")

                options = UiAutomator2Options()
                options.platform_name = "Android"
                options.udid = device.udid
                options.automation_name = "UiAutomator2"
                options.app_package = apk.package_name
                options.app_activity = apk.launch_activity
                options.no_reset = True
                options.auto_grant_permissions = True
                options.new_command_timeout = 120

                driver = webdriver.Remote(device.appium_server_url, options=options)
                on_step = _make_step_persister(session, storage, run_id=run.id, case=case)
                try:
                    tools = AndroidTools(driver, package_name=apk.package_name)
                    client = build_agent_client(settings)
                    try:
                        case_result = run_case_with_android_agent(
                            client,
                            tools=tools,
                            feature=case.feature,
                            scenario=case.scenario,
                            steps=list(case.steps),
                            expected_result=case.expected_result,
                            app_label=apk.label or apk.package_name,
                            resolve_secret=resolve_secret,
                            model=settings.ai_model_generation,
                            on_step=on_step,
                        )
                    except AgentClientError as exc:
                        case_result = CaseRunResult(
                            status=TestStatus.BLOCKED,
                            actual_result=f"Agent error: {exc}",
                            confidence=0.0,
                        )
                finally:
                    driver.quit()

                status = case_result.status
                actual_result = case_result.actual_result
                crash_context = _check_for_crash(adb_path, device.udid, apk.package_name)
                if crash_context:
                    status = TestStatus.FAILED
                    actual_result = f"App crashed during this case. {actual_result}".strip()
                    on_step(
                        CaseStepEvent(
                            seq=len(case_result.steps) + 1,
                            action="crash_detected",
                            target=apk.package_name,
                            input_masked=None,
                            assertion=None,
                            outcome=RunStepOutcome.ERROR,
                            message=crash_context[:2000],
                            screenshot=None,
                            duration_ms=0,
                        )
                    )

                results[str(case.id)] = {
                    "status": status.value,
                    "actual_result": actual_result,
                    "confidence": case_result.confidence,
                    "mode": "agent",
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

        if sink.events:
            session.add(
                UsageRecord(
                    feature="execution_run",
                    entity_id=str(run_id),
                    model=settings.ai_model_generation,
                    prompt_tokens=sink.prompt_tokens,
                    completion_tokens=sink.completion_tokens,
                )
            )

        if cancelled:
            run.status = RunStatus.CANCELLED
        elif counts["failed"] == 0 and counts["blocked"] == 0:
            run.status = RunStatus.PASSED
        else:
            run.status = RunStatus.FAILED
        run.finished_at = utcnow()
        RUN_DURATION.labels(target="android", status=run.status.value).observe(
            run_duration_seconds(run.started_at, run.finished_at)
        )
        run.summary_json = {"total": len(ordered_cases), **counts, "cases": results}
        session.commit()
        publish(str(run_id), {"type": "run_done", "status": run.status.value})
    except Exception as exc:
        logger.exception("Android run %s failed", run_id)
        run.status = RunStatus.ERROR
        run.error = str(exc)[:2000]
        run.finished_at = utcnow()
        RUN_DURATION.labels(target="android", status="error").observe(
            run_duration_seconds(run.started_at, run.finished_at)
        )
        session.commit()
        publish(str(run_id), {"type": "run_done", "status": "error", "error": str(exc)[:500]})
    finally:
        if device is not None and package_name is not None:
            try:
                _adb(settings.android_adb_path, "-s", device.udid, "uninstall", package_name)
            except Exception:
                logger.exception("Could not uninstall %s after run %s", package_name, run_id)
        clear_cancel(str(run_id))
        session.close()


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
