"""End-to-end Android Test Lab run: upload & analyze a real APK, run a case against a real
emulator with a FakeAgentClient, apply, and confirm evidence (including a crash-detected
case, to prove the logcat-based auto-fail actually works against a real crash)."""

import time

import pytest
from fastapi.testclient import TestClient

from app.services.execution.agent_client import AgentReply, FakeAgentClient, ToolCall


def _wait_for_run(client: TestClient, run_id: str, *, timeout: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/runs/{run_id}").json()
        if run["status"] not in ("queued", "running"):
            return run
        time.sleep(0.5)
    raise AssertionError(f"Run {run_id} did not finish within {timeout}s")


def _setup_suite_and_apk(
    admin_client: TestClient, android_apk_path: str
) -> tuple[dict, dict, dict]:
    project = admin_client.post(
        "/api/v1/projects",
        json={"name": "Android QA", "app_code": "ANDROIDQA", "id_prefix": "AndroidQA"},
    ).json()
    type_obj = admin_client.post("/api/v1/admin/types", json={"name": "Android"}).json()
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "ApiDemos Suite",
            "header": {"project_name_line": "ANDROIDQA: ApiDemos"},
        },
    ).json()
    with open(android_apk_path, "rb") as f:
        apk_resp = admin_client.post(
            f"/api/v1/projects/{project['id']}/apks",
            files={"file": ("ApiDemos-debug.apk", f, "application/vnd.android.package-archive")},
        )
    assert apk_resp.status_code == 201, apk_resp.text
    apk = apk_resp.json()
    return project, suite, apk


@pytest.mark.usefixtures("android_device_udid")
def test_apk_upload_analyzes_package_info(admin_client: TestClient, android_apk_path: str) -> None:
    _, _, apk = _setup_suite_and_apk(admin_client, android_apk_path)
    assert apk["package_name"] == "io.appium.android.apis"
    assert apk["launch_activity"] == ".ApiDemos"
    assert apk["label"] == "API Demos"


@pytest.mark.usefixtures("android_device_udid")
def test_full_android_run_navigate_apply_and_evidence(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch, android_apk_path: str
) -> None:
    _, suite, apk = _setup_suite_and_apk(admin_client, android_apk_path)

    case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "Navigation",
            "scenario": "Check that tapping Views shows the Animation entry",
            "steps": ["Tap the Views category.", "Confirm Animation is visible."],
            "expected_result": "The Views sub-menu, including Animation, is shown.",
        },
    ).json()

    turns = [
        AgentReply(tool_calls=[ToolCall(id="c1", name="snapshot", arguments={})]),
        # The agent doesn't know the ref ahead of time in a fake run, so this test drives a
        # deterministic trace: tap whatever ref the snapshot step would have offered for
        # "Views" is not knowable without a real LLM loop, so we assert on screen text
        # instead of tapping — a lighter but still-real check of the live snapshot content.
        AgentReply(
            tool_calls=[
                ToolCall(id="c2", name="assert_visible", arguments={"text": "Views"}),
            ]
        ),
        AgentReply(
            tool_calls=[
                ToolCall(
                    id="c3",
                    name="finish",
                    arguments={
                        "status": "Passed",
                        "actual_result": "The Views entry is visible on the main screen.",
                        "confidence": 0.9,
                    },
                )
            ]
        ),
    ]
    fake_client = FakeAgentClient(turns=turns)
    monkeypatch.setattr(
        "app.services.execution.android_execution_runner.build_agent_client",
        lambda settings: fake_client,
    )

    created = admin_client.post(
        "/api/v1/runs",
        json={
            "suite_id": suite["id"],
            "target": "android",
            "case_ids": [case["id"]],
            "apk_id": apk["id"],
        },
    ).json()
    assert created["status"] == "queued"
    run = _wait_for_run(admin_client, created["id"])
    assert run["status"] == "passed", run

    result = run["summary_json"]["cases"][case["id"]]
    assert result["status"] == "Passed"
    assert result["mode"] == "agent"
    assert result["applied"] is False

    cases_before = {
        c["id"]: c for c in admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    }
    assert cases_before[case["id"]]["status"] == "Not Tested"

    applied = admin_client.post(f"/api/v1/runs/{run['id']}/apply", json={}).json()
    assert applied["summary_json"]["cases"][case["id"]]["applied"] is True

    cases_after = {
        c["id"]: c for c in admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    }
    assert cases_after[case["id"]]["status"] == "Passed"
    assert cases_after[case["id"]]["execution_mode"] == "automated"

    evidence = admin_client.get(f"/api/v1/cases/{case['id']}/evidence").json()
    assert len(evidence) >= 1
    file_resp = admin_client.get(f"/api/v1/evidence/{evidence[0]['id']}/file")
    assert file_resp.status_code == 200
    assert file_resp.content[:8] == b"\x89PNG\r\n\x1a\n"


def test_crash_during_case_auto_fails_regardless_of_agent_verdict(
    admin_client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    android_apk_path: str,
    android_device_udid: str,
) -> None:
    """Drives a real crash of the running app process via `adb shell am crash` and asserts
    the runner's logcat-based detection catches it even though the fake agent confidently
    reports "Passed" — proving the crash check overrides the agent's self-reported result,
    not just that the agent loop itself can report Failed."""
    import subprocess

    from app.core.config import get_settings

    _, suite, apk = _setup_suite_and_apk(admin_client, android_apk_path)
    case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "Crash handling",
            "scenario": "Check that a crash is detected even if the agent misreports success",
            "steps": ["(the app is force-crashed by the test itself)"],
            "expected_result": "This case should be marked Failed due to the crash.",
        },
    ).json()

    settings = get_settings()

    class CrashingThenFinishingAgent:
        """First tool call deliberately crashes the app process via adb, then reports a
        (wrong) Passed verdict."""

        def __init__(self) -> None:
            self.step = 0

        def next_turn(self, *, messages, tools, model, temperature, max_tokens):
            self.step += 1
            if self.step == 1:
                subprocess.run(
                    [
                        settings.android_adb_path,
                        "-s",
                        android_device_udid,
                        "shell",
                        "am",
                        "crash",
                        apk["package_name"],
                    ],
                    capture_output=True,
                    timeout=15,
                )
                return AgentReply(tool_calls=[ToolCall(id="c1", name="snapshot", arguments={})])
            return AgentReply(
                tool_calls=[
                    ToolCall(
                        id="c2",
                        name="finish",
                        arguments={
                            "status": "Passed",
                            "actual_result": "Looked fine to me.",
                            "confidence": 0.9,
                        },
                    )
                ]
            )

    monkeypatch.setattr(
        "app.services.execution.android_execution_runner.build_agent_client",
        lambda settings_arg: CrashingThenFinishingAgent(),
    )

    created = admin_client.post(
        "/api/v1/runs",
        json={
            "suite_id": suite["id"],
            "target": "android",
            "case_ids": [case["id"]],
            "apk_id": apk["id"],
        },
    ).json()
    run = _wait_for_run(admin_client, created["id"])

    result = run["summary_json"]["cases"][case["id"]]
    assert result["status"] == "Failed", result
    assert "crash" in result["actual_result"].lower()
