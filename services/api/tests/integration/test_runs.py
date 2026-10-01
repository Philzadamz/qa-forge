"""Validation-only Test Lab run tests (no real execution — see tests/execution/ for the full
agent-mode + deterministic-routine run against a real browser and infra/demo-target)."""

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> dict:
    return client.post(
        "/api/v1/projects",
        json={
            "name": "Kusala",
            "app_code": "KUSALA",
            "id_prefix": "Kusala",
            "default_test_url": "http://127.0.0.1:9/login",
        },
    ).json()


def _create_type(admin_client: TestClient) -> dict:
    return admin_client.post("/api/v1/admin/types", json={"name": "Web Application"}).json()


def _create_suite(client: TestClient, project: dict, type_obj: dict) -> dict:
    return client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "Suite",
            "header": {"project_name_line": "KUSALA: Suite"},
        },
    ).json()


def test_create_run_rejects_android_target(admin_client: TestClient) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type(admin_client)
    suite = _create_suite(admin_client, project, type_obj)
    case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "f",
            "scenario": "s",
            "steps": ["x"],
            "expected_result": "e",
        },
    ).json()

    resp = admin_client.post(
        "/api/v1/runs",
        json={"suite_id": suite["id"], "case_ids": [case["id"]], "target": "android"},
    )
    assert resp.status_code == 400
    assert "Web" in resp.text


def test_create_api_run_rejects_case_without_request_plan(admin_client: TestClient) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type(admin_client)
    suite = _create_suite(admin_client, project, type_obj)
    case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "f",
            "scenario": "s",
            "steps": ["x"],
            "expected_result": "e",
        },
    ).json()

    resp = admin_client.post(
        "/api/v1/runs",
        json={"suite_id": suite["id"], "case_ids": [case["id"]], "target": "api"},
    )
    assert resp.status_code == 400
    assert "request plan" in resp.text


def test_create_run_rejects_case_not_in_suite(admin_client: TestClient) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type(admin_client)
    suite_a = _create_suite(admin_client, project, type_obj)
    suite_b = _create_suite(admin_client, project, type_obj)
    case_in_b = admin_client.post(
        f"/api/v1/suites/{suite_b['id']}/cases",
        json={
            "section": "functional",
            "feature": "f",
            "scenario": "s",
            "steps": ["x"],
            "expected_result": "e",
        },
    ).json()

    resp = admin_client.post(
        "/api/v1/runs", json={"suite_id": suite_a["id"], "case_ids": [case_in_b["id"]]}
    )
    assert resp.status_code == 400


def test_create_run_requires_a_target_url(admin_client: TestClient) -> None:
    project = admin_client.post(
        "/api/v1/projects", json={"name": "NoURL", "app_code": "NOURL", "id_prefix": "NoURL"}
    ).json()
    type_obj = _create_type(admin_client)
    suite = _create_suite(admin_client, project, type_obj)
    case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "f",
            "scenario": "s",
            "steps": ["x"],
            "expected_result": "e",
        },
    ).json()

    resp = admin_client.post(
        "/api/v1/runs", json={"suite_id": suite["id"], "case_ids": [case["id"]]}
    )
    assert resp.status_code == 400
    assert "target URL" in resp.text


def test_apply_before_run_finishes_is_rejected(admin_client: TestClient) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type(admin_client)
    suite = _create_suite(admin_client, project, type_obj)
    case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "f",
            "scenario": "s",
            "steps": ["x"],
            "expected_result": "e",
        },
    ).json()
    run = admin_client.post(
        "/api/v1/runs", json={"suite_id": suite["id"], "case_ids": [case["id"]]}
    ).json()
    assert run["status"] == "queued"

    resp = admin_client.post(f"/api/v1/runs/{run['id']}/apply", json={})
    assert resp.status_code == 400


def test_cancel_marks_queued_run_for_cancellation_without_error(admin_client: TestClient) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type(admin_client)
    suite = _create_suite(admin_client, project, type_obj)
    case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "f",
            "scenario": "s",
            "steps": ["x"],
            "expected_result": "e",
        },
    ).json()
    run = admin_client.post(
        "/api/v1/runs", json={"suite_id": suite["id"], "case_ids": [case["id"]]}
    ).json()

    resp = admin_client.post(f"/api/v1/runs/{run['id']}/cancel")
    assert resp.status_code == 200
