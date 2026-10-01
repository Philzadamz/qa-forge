from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import make_user


def _create_project(client: TestClient, name: str = "Kusala") -> dict:
    resp = client.post(
        "/api/v1/projects",
        json={"name": name, "app_code": "KUSALA", "id_prefix": "Kusala"},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_and_get_project(user_client: TestClient) -> None:
    created = _create_project(user_client)
    assert created["app_code"] == "KUSALA"
    assert created["members"] == []

    resp = user_client.get(f"/api/v1/projects/{created['id']}")
    assert resp.status_code == 200
    assert resp.json()["id"] == created["id"]


def test_user_cannot_see_another_users_project(client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="owner@example.com", password="owner-password-1", role="user")
    client.post(
        "/api/v1/auth/login", json={"email": "owner@example.com", "password": "owner-password-1"}
    )
    owned = _create_project(client, "Owner's Project")
    client.post("/api/v1/auth/logout")

    make_user(db_session, email="other@example.com", password="other-password-1", role="user")
    client.post(
        "/api/v1/auth/login", json={"email": "other@example.com", "password": "other-password-1"}
    )

    resp = client.get(f"/api/v1/projects/{owned['id']}")
    assert resp.status_code == 403

    listing = client.get("/api/v1/projects").json()
    assert all(p["id"] != owned["id"] for p in listing)


def test_admin_sees_all_projects_and_can_reassign_owner(
    admin_client: TestClient, db_session: Session
) -> None:
    make_user(db_session, email="owner2@example.com", password="owner-password-1", role="user")
    new_owner = make_user(
        db_session, email="new-owner@example.com", password="new-owner-password-1", role="user"
    )

    admin_client.post(
        "/api/v1/auth/login", json={"email": "owner2@example.com", "password": "owner-password-1"}
    )
    owned = _create_project(admin_client, "Reassign Me")

    admin_client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    listing = admin_client.get("/api/v1/projects").json()
    assert any(p["id"] == owned["id"] for p in listing)

    resp = admin_client.patch(
        f"/api/v1/projects/{owned['id']}", json={"owner_id": str(new_owner.id)}
    )
    assert resp.status_code == 200
    assert resp.json()["owner_id"] == str(new_owner.id)


def test_non_admin_cannot_reassign_owner(user_client: TestClient) -> None:
    created = _create_project(user_client)
    resp = user_client.patch(
        f"/api/v1/projects/{created['id']}",
        json={"owner_id": "00000000-0000-0000-0000-000000000000"},
    )
    assert resp.status_code == 403


def test_delete_project_is_soft_delete(user_client: TestClient) -> None:
    created = _create_project(user_client)
    resp = user_client.delete(f"/api/v1/projects/{created['id']}")
    assert resp.status_code == 204

    resp = user_client.get(f"/api/v1/projects/{created['id']}")
    assert resp.status_code == 404


def test_member_can_access_project_they_do_not_own(client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="owner3@example.com", password="owner-password-1", role="user")
    client.post(
        "/api/v1/auth/login", json={"email": "owner3@example.com", "password": "owner-password-1"}
    )
    member = make_user(
        db_session, email="member@example.com", password="member-password-1", role="user"
    )
    resp = client.post(
        "/api/v1/projects",
        json={
            "name": "Shared Project",
            "app_code": "SHARE",
            "id_prefix": "Share",
            "members": [str(member.id)],
        },
    )
    project = resp.json()
    client.post("/api/v1/auth/logout")

    client.post(
        "/api/v1/auth/login", json={"email": "member@example.com", "password": "member-password-1"}
    )
    resp = client.get(f"/api/v1/projects/{project['id']}")
    assert resp.status_code == 200
