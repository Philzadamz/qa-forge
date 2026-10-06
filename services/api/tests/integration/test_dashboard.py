import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.project import Project
from app.models.test_case_type import TestCaseType
from app.models.test_suite import TestSuite
from app.models.usage_record import UsageRecord
from tests.conftest import make_user


def test_dashboard_is_empty_for_a_new_user(user_client: TestClient) -> None:
    resp = user_client.get("/api/v1/dashboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_count"] == 0
    assert body["suite_count"] == 0
    assert body["recent_runs"] == []
    assert body["usage"]["prompt_tokens"] == 0
    assert body["usage"]["cost_estimate"] == 0.0


def test_dashboard_counts_own_projects_and_suites(
    user_client: TestClient, db_session: Session
) -> None:
    project_resp = user_client.post(
        "/api/v1/projects", json={"name": "Kusala", "app_code": "KUSALA", "id_prefix": "Kusala"}
    )
    assert project_resp.status_code == 201
    project_id = project_resp.json()["id"]

    type_obj = TestCaseType(name=f"T-{uuid.uuid4().hex[:6]}")
    db_session.add(type_obj)
    db_session.flush()
    db_session.add(TestSuite(project_id=uuid.UUID(project_id), type_id=type_obj.id, name="S"))
    db_session.commit()

    body = user_client.get("/api/v1/dashboard").json()
    assert body["project_count"] == 1
    assert body["suite_count"] == 1


def test_dashboard_hides_usage_from_projects_the_caller_cannot_see(
    user_client: TestClient, db_session: Session
) -> None:
    owner = make_user(db_session, email="someone-else@example.com")
    foreign_project = Project(name="Foreign", app_code="F", id_prefix="F", owner_id=owner.id)
    db_session.add(foreign_project)
    db_session.flush()
    type_obj = TestCaseType(name=f"T-{uuid.uuid4().hex[:6]}")
    db_session.add(type_obj)
    db_session.flush()
    foreign_suite = TestSuite(project_id=foreign_project.id, type_id=type_obj.id, name="X")
    db_session.add(foreign_suite)
    db_session.flush()
    db_session.add(
        UsageRecord(
            feature="report_draft",
            entity_id=str(foreign_suite.id),
            model="deepseek-chat",
            prompt_tokens=5000,
            completion_tokens=800,
        )
    )
    db_session.commit()

    body = user_client.get("/api/v1/dashboard").json()
    assert body["usage"]["prompt_tokens"] == 0
    assert body["project_count"] == 0


def test_dashboard_attributes_usage_to_the_caller_own_project(
    user_client: TestClient, db_session: Session
) -> None:
    project_resp = user_client.post(
        "/api/v1/projects", json={"name": "Mine", "app_code": "MINE", "id_prefix": "Mine"}
    )
    project_id = uuid.UUID(project_resp.json()["id"])
    type_obj = TestCaseType(name=f"T-{uuid.uuid4().hex[:6]}")
    db_session.add(type_obj)
    db_session.flush()
    suite = TestSuite(project_id=project_id, type_id=type_obj.id, name="Mine")
    db_session.add(suite)
    db_session.flush()
    db_session.add(
        UsageRecord(
            feature="api_case_generation",
            entity_id=str(suite.id),
            model="deepseek-chat",
            prompt_tokens=1200,
            completion_tokens=300,
        )
    )
    db_session.commit()

    body = user_client.get("/api/v1/dashboard").json()
    assert body["usage"]["prompt_tokens"] == 1200
    assert body["usage"]["completion_tokens"] == 300
    assert body["usage"]["by_feature"] == [
        {"feature": "api_case_generation", "prompt_tokens": 1200, "completion_tokens": 300}
    ]


def test_dashboard_counts_recent_runs_and_pass_rate(
    user_client: TestClient, db_session: Session
) -> None:
    from app.core.enums import RunStatus, RunTarget
    from app.models.test_run import TestRun

    project_resp = user_client.post(
        "/api/v1/projects", json={"name": "Runs", "app_code": "RUNS", "id_prefix": "Runs"}
    )
    project_id = uuid.UUID(project_resp.json()["id"])
    type_obj = TestCaseType(name=f"T-{uuid.uuid4().hex[:6]}")
    db_session.add(type_obj)
    db_session.flush()
    suite = TestSuite(project_id=project_id, type_id=type_obj.id, name="Runs suite")
    db_session.add(suite)
    db_session.flush()
    db_session.add_all(
        [
            TestRun(
                project_id=project_id,
                suite_id=suite.id,
                target=RunTarget.WEB,
                status=RunStatus.PASSED,
                summary_json={"total": 2, "passed": 2, "failed": 0},
            ),
            TestRun(
                project_id=project_id,
                suite_id=suite.id,
                target=RunTarget.WEB,
                status=RunStatus.FAILED,
                summary_json={"total": 2, "passed": 1, "failed": 1},
            ),
        ]
    )
    db_session.commit()

    body = user_client.get("/api/v1/dashboard").json()
    assert body["run_count_30_days"] == 2
    assert body["pass_rate_30_days"] == 0.5
    assert len(body["recent_runs"]) == 2
    assert body["recent_runs"][0]["suite_name"] == "Runs suite"
