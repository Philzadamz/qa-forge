from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import make_user


def _create_project(client: TestClient) -> dict:
    return client.post(
        "/api/v1/projects", json={"name": "Kusala", "app_code": "KUSALA", "id_prefix": "Kusala"}
    ).json()


def _create_type_with_defaults(admin_client: TestClient, n: int = 3) -> dict:
    type_obj = admin_client.post("/api/v1/admin/types", json={"name": "Web Application"}).json()
    for i in range(n):
        admin_client.post(
            f"/api/v1/admin/types/{type_obj['id']}/defaults",
            json={
                "feature": f"Feature {i}",
                "scenario": f"Check default scenario {i}",
                "steps": ["Step 1"],
                "expected_result": "Expected",
            },
        )
    return type_obj


def _suite_header() -> dict:
    return {"project_name_line": "KUSALA: Test Suite"}


def test_create_suite_snapshots_defaults_and_numbers_them(
    admin_client: TestClient, db_session: Session
) -> None:
    make_user(db_session, email="qa@example.com", password="qa-password-1", role="user")
    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "qa-password-1"}
    )
    project = _create_project(admin_client)
    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    type_obj = _create_type_with_defaults(admin_client, n=3)

    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "qa-password-1"}
    )
    resp = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "My Suite",
            "header": _suite_header(),
        },
    )
    assert resp.status_code == 201, resp.text
    suite = resp.json()

    cases = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    assert len(cases) == 3
    assert [c["display_id"] for c in cases] == ["Kusala_001", "Kusala_002", "Kusala_003"]
    assert all(c["section"] == "default" for c in cases)
    assert all(c["source"] == "default" for c in cases)


def test_excluding_a_default_renumbers_subsequent_cases(
    admin_client: TestClient, db_session: Session
) -> None:
    make_user(db_session, email="qa2@example.com", password="qa-password-1", role="user")
    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa2@example.com", "password": "qa-password-1"}
    )
    project = _create_project(admin_client)
    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    type_obj = _create_type_with_defaults(admin_client, n=3)

    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa2@example.com", "password": "qa-password-1"}
    )
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": _suite_header(),
        },
    ).json()
    cases = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()

    resp = admin_client.patch(f"/api/v1/cases/{cases[0]['id']}", json={"included": False})
    assert resp.status_code == 200
    assert resp.json()["display_id"] == ""

    remaining = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    included = [c for c in remaining if c["included"]]
    assert [c["display_id"] for c in included] == ["Kusala_001", "Kusala_002"]


def test_manual_case_numbering_continues_after_defaults(
    admin_client: TestClient, db_session: Session
) -> None:
    make_user(db_session, email="qa3@example.com", password="qa-password-1", role="user")
    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa3@example.com", "password": "qa-password-1"}
    )
    project = _create_project(admin_client)
    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    type_obj = _create_type_with_defaults(admin_client, n=2)

    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa3@example.com", "password": "qa-password-1"}
    )
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": _suite_header(),
        },
    ).json()

    resp = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "Manual Feature",
            "scenario": "Check manual case",
            "steps": ["Do it"],
            "expected_result": "It happens",
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["display_id"] == "Kusala_003"


def test_suite_requires_active_type(user_client: TestClient) -> None:
    project = _create_project(user_client)
    resp = user_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": "00000000-0000-0000-0000-000000000000",
            "name": "S",
            "header": _suite_header(),
        },
    )
    assert resp.status_code == 400


def test_delete_case_renumbers(admin_client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="qa4@example.com", password="qa-password-1", role="user")
    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa4@example.com", "password": "qa-password-1"}
    )
    project = _create_project(admin_client)
    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    type_obj = _create_type_with_defaults(admin_client, n=3)

    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa4@example.com", "password": "qa-password-1"}
    )
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": _suite_header(),
        },
    ).json()
    cases = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()

    resp = admin_client.delete(f"/api/v1/cases/{cases[0]['id']}")
    assert resp.status_code == 204

    remaining = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    assert len(remaining) == 2
    assert [c["display_id"] for c in remaining] == ["Kusala_001", "Kusala_002"]


def test_bulk_mark_cases_as_passed(admin_client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="qa5@example.com", password="qa-password-1", role="user")
    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa5@example.com", "password": "qa-password-1"}
    )
    project = _create_project(admin_client)
    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    type_obj = _create_type_with_defaults(admin_client, n=3)

    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa5@example.com", "password": "qa-password-1"}
    )
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": _suite_header(),
        },
    ).json()
    cases = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()

    resp = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases/bulk",
        json={
            "case_ids": [c["id"] for c in cases],
            "status": "Passed",
            "actual_result": "As expected",
        },
    )
    assert resp.status_code == 200, resp.text
    updated = resp.json()
    assert all(c["status"] == "Passed" for c in updated)
    assert all(c["actual_result"] == "As expected" for c in updated)


def test_bulk_update_rejects_case_from_another_suite(
    admin_client: TestClient, db_session: Session
) -> None:
    make_user(db_session, email="qa6@example.com", password="qa-password-1", role="user")
    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa6@example.com", "password": "qa-password-1"}
    )
    project = _create_project(admin_client)
    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    type_obj = _create_type_with_defaults(admin_client, n=1)

    admin_client.post(
        "/api/v1/auth/login", json={"email": "qa6@example.com", "password": "qa-password-1"}
    )
    suite_a = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "A",
            "header": _suite_header(),
        },
    ).json()
    suite_b = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "B",
            "header": _suite_header(),
        },
    ).json()
    case_b = admin_client.get(f"/api/v1/suites/{suite_b['id']}/cases").json()[0]

    resp = admin_client.post(
        f"/api/v1/suites/{suite_a['id']}/cases/bulk",
        json={"case_ids": [case_b["id"]], "status": "Passed"},
    )
    assert resp.status_code == 400
