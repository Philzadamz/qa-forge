import uuid

from fastapi.testclient import TestClient


def _create_project(client: TestClient) -> dict:
    return client.post(
        "/api/v1/projects", json={"name": "Kusala", "app_code": "KUSALA", "id_prefix": "Kusala"}
    ).json()


def _create_suite_with_case(admin_client: TestClient) -> tuple[dict, dict]:
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
            "name": "S",
            "header": {"project_name_line": "X"},
        },
    ).json()
    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]
    return suite, case


def test_create_list_update_delete_bug(admin_client: TestClient) -> None:
    suite, case = _create_suite_with_case(admin_client)

    created = admin_client.post(
        f"/api/v1/suites/{suite['id']}/bugs",
        json={"test_case_id": case["id"], "title": "Login fails", "severity": "High"},
    )
    assert created.status_code == 201, created.text
    bug = created.json()
    assert bug["status"] == "open"

    listing = admin_client.get(f"/api/v1/suites/{suite['id']}/bugs").json()
    assert len(listing) == 1

    patched = admin_client.patch(f"/api/v1/bugs/{bug['id']}", json={"status": "fixed"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "fixed"

    deleted = admin_client.delete(f"/api/v1/bugs/{bug['id']}")
    assert deleted.status_code == 204
    assert admin_client.get(f"/api/v1/suites/{suite['id']}/bugs").json() == []


def test_bug_test_case_must_belong_to_suite(admin_client: TestClient) -> None:
    suite, _ = _create_suite_with_case(admin_client)
    _, other_case = _create_suite_with_case(admin_client)

    resp = admin_client.post(
        f"/api/v1/suites/{suite['id']}/bugs",
        json={"test_case_id": other_case["id"], "title": "Mismatched case"},
    )
    assert resp.status_code == 400


def test_draft_bug_from_failed_case(admin_client: TestClient) -> None:
    _, case = _create_suite_with_case(admin_client)
    admin_client.patch(
        f"/api/v1/cases/{case['id']}",
        json={"status": "Failed", "actual_result": "Login button did nothing."},
    )

    resp = admin_client.post(f"/api/v1/cases/{case['id']}/bugs/draft")
    assert resp.status_code == 201, resp.text
    bug = resp.json()
    assert case["display_id"] in bug["title"] or case["feature"] in bug["title"]
    assert "Login button did nothing." in bug["description"]
    assert bug["test_case_id"] == case["id"]
