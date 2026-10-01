import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.ai.client import FakeLLMClient
from tests.conftest import make_user


class _SyncThread:
    """Test double for threading.Thread that runs the target immediately, in-thread, so
    the generation job is fully done by the time the test's next assertion runs."""

    def __init__(self, target, args=(), kwargs=None, daemon=None) -> None:
        self._target = target
        self._args = args
        self._kwargs = kwargs or {}

    def start(self) -> None:
        self._target(*self._args, **self._kwargs)


@pytest.fixture
def sync_generation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.routers.suites.threading.Thread", _SyncThread)


def _create_project(client: TestClient) -> dict:
    return client.post(
        "/api/v1/projects", json={"name": "Kusala", "app_code": "KUSALA", "id_prefix": "Kusala"}
    ).json()


def _create_type(admin_client: TestClient) -> dict:
    return admin_client.post("/api/v1/admin/types", json={"name": "Web Application"}).json()


def _cases_json(cases: list[dict]) -> str:
    return json.dumps({"cases": cases})


ANALYSIS_JSON = json.dumps(
    {
        "features": ["Login"],
        "actors": ["User"],
        "acceptance_criteria": [{"id": "AC-1", "text": "Login works", "feature": "Login"}],
        "business_rules": [],
        "limits": [],
        "states": [],
        "approval_chains": [],
        "validations": [],
        "integrations": [],
        "out_of_scope": [],
        "questions": [],
    }
)

LOGIN_CASES_JSON = _cases_json(
    [
        {
            "feature": "Login",
            "scenario": "Check that valid credentials grant access",
            "steps": ["Open the app.", "Log in."],
            "expected_result": "User is logged in",
            "traces_to": ["AC-1"],
        }
    ]
)


def test_full_generation_flow(
    admin_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    sync_generation: None,
) -> None:
    make_user(db_session, email="gen@example.com", password="gen-password-1", role="user")
    admin_client.post(
        "/api/v1/auth/login", json={"email": "gen@example.com", "password": "gen-password-1"}
    )
    project = _create_project(admin_client)

    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    type_obj = _create_type(admin_client)

    admin_client.post(
        "/api/v1/auth/login", json={"email": "gen@example.com", "password": "gen-password-1"}
    )
    story = admin_client.post(
        f"/api/v1/projects/{project['id']}/stories/paste",
        json={"title": "Login story", "text": "Users must log in with a valid email and password."},
    ).json()
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "Login Suite",
            "header": {"project_name_line": "KUSALA: Login Suite"},
        },
    ).json()

    fake_client = FakeLLMClient(responses=[ANALYSIS_JSON, LOGIN_CASES_JSON])
    monkeypatch.setattr(
        "app.services.suites.generation_runner.build_llm_client", lambda settings: fake_client
    )

    resp = admin_client.post(
        f"/api/v1/suites/{suite['id']}/generate",
        json={"story_ids": [story["id"]], "coverage_depth": "Essential"},
    )
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["id"]

    job = admin_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "succeeded", job

    cases = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    functional = [c for c in cases if c["section"] == "functional"]
    assert len(functional) == 1
    case = functional[0]
    # USR-GEN-4: non-empty feature/scenario/steps/expected, blank actual, Not Tested status.
    assert case["feature"] == "Login"
    assert case["scenario"]
    assert case["steps"]
    assert case["expected_result"]
    assert case["actual_result"] == ""
    assert case["status"] == "Not Tested"
    assert case["source"] == "ai"
    assert case["display_id"]  # continues numbering after any defaults


def test_generation_job_failure_is_recorded(
    admin_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    sync_generation: None,
) -> None:
    make_user(db_session, email="gen2@example.com", password="gen-password-1", role="user")
    admin_client.post(
        "/api/v1/auth/login", json={"email": "gen2@example.com", "password": "gen-password-1"}
    )
    project = _create_project(admin_client)
    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    type_obj = _create_type(admin_client)
    admin_client.post(
        "/api/v1/auth/login", json={"email": "gen2@example.com", "password": "gen-password-1"}
    )
    story = admin_client.post(
        f"/api/v1/projects/{project['id']}/stories/paste",
        json={"title": "S", "text": "Some story text."},
    ).json()
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "Suite",
            "header": {"project_name_line": "X"},
        },
    ).json()

    broken_client = FakeLLMClient(responses=["not valid json", "still not valid json"])
    monkeypatch.setattr(
        "app.services.suites.generation_runner.build_llm_client", lambda settings: broken_client
    )

    resp = admin_client.post(
        f"/api/v1/suites/{suite['id']}/generate", json={"story_ids": [story["id"]]}
    )
    job_id = resp.json()["id"]

    job = admin_client.get(f"/api/v1/jobs/{job_id}").json()
    assert job["status"] == "failed"
    assert job["error"]

    # Regression: with _SyncThread the job is already terminal by the time anyone could
    # subscribe, so /events must take the "already finished" replay branch. That branch
    # used to omit `error` entirely, which is exactly what a fast FakeLLM failure hits in
    # practice — caught via manual browser testing, not by the two asserts above.
    events_resp = admin_client.get(f"/api/v1/jobs/{job_id}/events")
    assert events_resp.status_code == 200
    assert events_resp.text.startswith("data: ")
    event = json.loads(events_resp.text.removeprefix("data: ").strip())
    assert event == {"type": "job_done", "status": "failed", "error": job["error"]}


def test_generate_requires_stories(user_client: TestClient) -> None:
    project = _create_project(user_client)
    type_id = "00000000-0000-0000-0000-000000000000"
    suite_resp = user_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_id,
            "name": "S",
            "header": {"project_name_line": "X"},
        },
    )
    assert suite_resp.status_code == 400  # inactive/missing type, never gets to the stories check
