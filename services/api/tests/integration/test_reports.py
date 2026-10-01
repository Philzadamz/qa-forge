import json
import uuid

import pytest
from fastapi.testclient import TestClient

from app.services.ai.client import FakeLLMClient
from tests.golden.fixtures_paths import needs_docx_template

DRAFT_JSON = json.dumps(
    {
        "feature_descriptions": [
            {"name": "Login", "description": "To confirm that users can log in."}
        ],
        "exceptions": [],
        "comments": ["Testing completed successfully."],
    }
)


def _create_project(client: TestClient) -> dict:
    return client.post(
        "/api/v1/projects", json={"name": "Kusala", "app_code": "KUSALA", "id_prefix": "Kusala"}
    ).json()


def _create_suite_all_passed(admin_client: TestClient) -> dict:
    project = _create_project(admin_client)
    type_name = f"Web Application {uuid.uuid4()}"
    type_obj = admin_client.post("/api/v1/admin/types", json={"name": type_name}).json()
    admin_client.post(
        f"/api/v1/admin/types/{type_obj['id']}/defaults",
        json={
            "feature": "Login",
            "scenario": "Check login",
            "steps": ["Log in."],
            "expected_result": "Logged in",
        },
    )
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "Report Suite",
            "header": {
                "project_name_line": "KUSALA: Report Suite",
                "endpoint_url": "http://example.com",
            },
        },
    ).json()
    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]
    admin_client.patch(
        f"/api/v1/cases/{case['id']}", json={"status": "Passed", "actual_result": "As expected"}
    )
    return suite


def test_draft_report_computes_numbers_deterministically(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    suite = _create_suite_all_passed(admin_client)
    fake_client = FakeLLMClient(responses=[DRAFT_JSON])
    monkeypatch.setattr("app.routers.reports.build_llm_client", lambda settings: fake_client)

    resp = admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft")
    assert resp.status_code == 201, resp.text
    report = resp.json()
    ra = report["fields_json"]["result_analysis"]
    assert ra["total"] == 1
    assert ra["passed"] == 1
    assert ra["failed"] == 0
    assert report["fields_json"]["certified"] is True
    assert report["version"] == 1


def test_draft_report_survives_ai_failure(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    suite = _create_suite_all_passed(admin_client)
    broken_client = FakeLLMClient(responses=["not json"])
    monkeypatch.setattr("app.routers.reports.build_llm_client", lambda settings: broken_client)

    resp = admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft")
    assert resp.status_code == 201, resp.text
    comments = resp.json()["fields_json"]["comments"]
    assert any("AI draft unavailable" in c for c in comments)


def test_second_draft_increments_version(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    suite = _create_suite_all_passed(admin_client)
    fake_client = FakeLLMClient(responses=[DRAFT_JSON, DRAFT_JSON])
    monkeypatch.setattr("app.routers.reports.build_llm_client", lambda settings: fake_client)

    first = admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft").json()
    second = admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft").json()
    assert first["version"] == 1
    assert second["version"] == 2

    listing = admin_client.get(f"/api/v1/suites/{suite['id']}/reports").json()
    assert len(listing) == 2


def test_update_report_fields(admin_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    suite = _create_suite_all_passed(admin_client)
    fake_client = FakeLLMClient(responses=[DRAFT_JSON])
    monkeypatch.setattr("app.routers.reports.build_llm_client", lambda settings: fake_client)
    report = admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft").json()

    fields = report["fields_json"]
    fields["jira_link"] = "https://example.atlassian.net/browse/ABC-1"
    resp = admin_client.put(f"/api/v1/reports/{report['id']}", json={"fields_json": fields})
    assert resp.status_code == 200
    assert resp.json()["fields_json"]["jira_link"] == "https://example.atlassian.net/browse/ABC-1"


@needs_docx_template
def test_render_report_docx(admin_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    suite = _create_suite_all_passed(admin_client)
    fake_client = FakeLLMClient(responses=[DRAFT_JSON])
    monkeypatch.setattr("app.routers.reports.build_llm_client", lambda settings: fake_client)
    report = admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft").json()

    resp = admin_client.post(f"/api/v1/reports/{report['id']}/render")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert len(resp.content) > 0


def test_render_blocks_when_suite_results_changed_since_draft(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    suite = _create_suite_all_passed(admin_client)
    fake_client = FakeLLMClient(responses=[DRAFT_JSON])
    monkeypatch.setattr("app.routers.reports.build_llm_client", lambda settings: fake_client)
    report = admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft").json()

    # Change a case's status after the draft was made — numbers are now stale.
    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]
    admin_client.patch(f"/api/v1/cases/{case['id']}", json={"status": "Failed"})

    resp = admin_client.post(f"/api/v1/reports/{report['id']}/render")
    assert resp.status_code == 409


@needs_docx_template
def test_render_with_override_bypasses_consistency_check(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    suite = _create_suite_all_passed(admin_client)
    fake_client = FakeLLMClient(responses=[DRAFT_JSON])
    monkeypatch.setattr("app.routers.reports.build_llm_client", lambda settings: fake_client)
    report = admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft").json()

    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]
    admin_client.patch(f"/api/v1/cases/{case['id']}", json={"status": "Failed"})

    fields = report["fields_json"]
    resp = admin_client.put(
        f"/api/v1/reports/{report['id']}",
        json={"fields_json": {**fields, "ra_overridden": True}},
    )
    assert resp.status_code == 400  # missing reason

    resp = admin_client.put(
        f"/api/v1/reports/{report['id']}",
        json={
            "fields_json": {
                **fields,
                "ra_overridden": True,
                "ra_override_reason": "Manually verified counts",
            }
        },
    )
    assert resp.status_code == 200

    render_resp = admin_client.post(f"/api/v1/reports/{report['id']}/render")
    assert render_resp.status_code == 200, render_resp.text
