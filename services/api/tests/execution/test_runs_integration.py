"""End-to-end Test Lab run: a deterministic-routine default case and an agent-mode manual
case, both executed against the real `infra/demo-target` app through a real headless
Chromium — then applied to the suite. Exercises the full vertical slice the Phase 5 DoD asks
for: agent mode + deterministic defaults run against infra/demo-target; results applied to
suite; evidence produced."""

import time

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.execution.agent_client import AgentReply, FakeAgentClient, ToolCall
from tests.conftest import make_user


def _wait_for_run(client: TestClient, run_id: str, *, timeout: float = 20.0) -> dict:
    """Unlike generation (`_SyncThread`, FakeLLMClient — no real I/O), a run spawns a real
    Playwright subprocess internally; globally monkeypatching `threading.Thread` to run
    synchronously would also break Playwright's own internal thread use (it manages its
    driver subprocess via asyncio, which spawns waitpid-handling threads). So this test lets
    the run's background thread actually run concurrently and polls for completion instead."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/runs/{run_id}").json()
        if run["status"] not in ("queued", "running"):
            return run
        time.sleep(0.1)
    raise AssertionError(f"Run {run_id} did not finish within {timeout}s")


def _agent_turns_for_login_case() -> list[AgentReply]:
    return [
        AgentReply(tool_calls=[ToolCall(id="c1", name="navigate", arguments={"url": "__URL__"})]),
        AgentReply(
            tool_calls=[
                ToolCall(id="c2", name="fill", arguments={"ref": "#username", "value": "demo"})
            ]
        ),
        AgentReply(
            tool_calls=[
                ToolCall(
                    id="c3",
                    name="fill",
                    arguments={"ref": "#password", "secret_ref": "demo_password"},
                )
            ]
        ),
        AgentReply(
            tool_calls=[ToolCall(id="c4", name="click", arguments={"ref": "button[type=submit]"})]
        ),
        AgentReply(
            tool_calls=[
                ToolCall(
                    id="c5", name="wait_for", arguments={"ref": "#welcome", "timeout_ms": 5000}
                )
            ]
        ),
        AgentReply(
            tool_calls=[
                ToolCall(
                    id="c6",
                    name="finish",
                    arguments={
                        "status": "Passed",
                        "actual_result": "Logged in and reached the dashboard.",
                        "confidence": 0.95,
                    },
                )
            ]
        ),
    ]


def test_run_agent_and_deterministic_cases_then_apply(
    admin_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    demo_target_url: str,
) -> None:
    make_user(db_session, email="qa@example.com", password="qa-password-1", role="user")
    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "qa-password-1"}
    )
    project = admin_client.post(
        "/api/v1/projects",
        json={
            "name": "Kusala",
            "app_code": "KUSALA",
            "id_prefix": "Kusala",
            "default_test_url": f"{demo_target_url}/login",
        },
    ).json()

    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    type_obj = admin_client.post("/api/v1/admin/types", json={"name": "Web Application"}).json()
    admin_client.post(
        f"/api/v1/admin/types/{type_obj['id']}/defaults",
        json={
            "feature": "Login",
            "scenario": "Check that valid credentials grant access",
            "steps": ["Open the app.", "Log in with valid credentials."],
            "expected_result": "User reaches the dashboard.",
            "tags": ["deterministic:login_valid"],
        },
    )

    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "qa-password-1"}
    )
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "Login Suite",
            "header": {"project_name_line": "KUSALA: Login Suite"},
        },
    ).json()
    default_case = next(
        c
        for c in admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
        if c["section"] == "default"
    )

    manual_case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "Login",
            "scenario": "Check login via the agent",
            "steps": ["Navigate to the login page.", "Log in with valid credentials."],
            "expected_result": "The dashboard is shown.",
        },
    ).json()

    admin_client.post(
        f"/api/v1/projects/{project['id']}/secrets",
        json={"name": "demo_password", "value": "Demo12345!", "kind": "password"},
    )

    turns = _agent_turns_for_login_case()
    turns[0].tool_calls[0].arguments["url"] = f"{demo_target_url}/login"
    fake_client = FakeAgentClient(turns=turns)
    monkeypatch.setattr(
        "app.services.execution.execution_runner.build_agent_client", lambda settings: fake_client
    )

    created = admin_client.post(
        "/api/v1/runs",
        json={
            "suite_id": suite["id"],
            "case_ids": [default_case["id"], manual_case["id"]],
            "target_url": f"{demo_target_url}/login",
        },
    ).json()
    run = _wait_for_run(admin_client, created["id"])
    assert run["status"] == "passed", run

    summary = run["summary_json"]
    assert summary["total"] == 2
    assert summary["passed"] == 2
    case_results = summary["cases"]
    assert case_results[default_case["id"]]["mode"] == "deterministic"
    assert case_results[manual_case["id"]]["mode"] == "agent"
    assert case_results[manual_case["id"]]["applied"] is False

    # Nothing written into the suite yet (PRD §7.6 review-before-apply).
    cases_before = {
        c["id"]: c for c in admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    }
    assert cases_before[manual_case["id"]]["status"] == "Not Tested"

    steps = admin_client.get(f"/api/v1/runs/{run['id']}/steps").json()
    assert any(s["test_case_id"] == manual_case["id"] and s["action"] == "finish" for s in steps)
    fill_steps = [
        s for s in steps if s["action"] == "fill" and s["test_case_id"] == manual_case["id"]
    ]
    assert any(s["input_masked"] == "[SECRET:demo_password]" for s in fill_steps)
    assert all("Demo12345!" not in (s["input_masked"] or "") for s in steps)
    assert all("Demo12345!" not in (s["message"] or "") for s in steps)

    applied = admin_client.post(f"/api/v1/runs/{run['id']}/apply", json={}).json()
    assert applied["summary_json"]["cases"][manual_case["id"]]["applied"] is True
    assert applied["summary_json"]["cases"][default_case["id"]]["applied"] is True

    cases_after = {
        c["id"]: c for c in admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    }
    assert cases_after[manual_case["id"]]["status"] == "Passed"
    assert cases_after[manual_case["id"]]["execution_mode"] == "automated"
    assert cases_after[default_case["id"]]["status"] == "Passed"

    evidence = admin_client.get(f"/api/v1/cases/{manual_case['id']}/evidence").json()
    assert len(evidence) >= 1
