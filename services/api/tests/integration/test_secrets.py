from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import make_user


def _create_project(client: TestClient, name: str = "Kusala") -> dict:
    resp = client.post(
        "/api/v1/projects", json={"name": name, "app_code": "KUSALA", "id_prefix": "Kusala"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_create_list_and_delete_secret(user_client: TestClient) -> None:
    project = _create_project(user_client)
    created = user_client.post(
        f"/api/v1/projects/{project['id']}/secrets",
        json={"name": "demo_password", "value": "hunter2", "kind": "password"},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "demo_password"
    assert "value" not in body
    assert "ciphertext" not in body
    assert "hunter2" not in str(body)

    listed = user_client.get(f"/api/v1/projects/{project['id']}/secrets").json()
    assert len(listed) == 1
    assert "hunter2" not in str(listed)

    resp = user_client.delete(f"/api/v1/secrets/{body['id']}")
    assert resp.status_code == 204
    assert user_client.get(f"/api/v1/projects/{project['id']}/secrets").json() == []


def test_duplicate_secret_name_in_same_project_is_rejected(user_client: TestClient) -> None:
    project = _create_project(user_client)
    payload = {"name": "demo_password", "value": "hunter2", "kind": "password"}
    user_client.post(f"/api/v1/projects/{project['id']}/secrets", json=payload)
    resp = user_client.post(f"/api/v1/projects/{project['id']}/secrets", json=payload)
    assert resp.status_code == 409


def test_secrets_response_never_includes_raw_db_value(user_client: TestClient) -> None:
    project = _create_project(user_client)
    resp = user_client.post(
        f"/api/v1/projects/{project['id']}/secrets",
        json={"name": "api_key", "value": "sk-super-secret-value", "kind": "api_key"},
    )
    assert "sk-super-secret-value" not in resp.text


def test_user_cannot_access_another_users_project_secrets(
    client: TestClient, db_session: Session
) -> None:
    make_user(db_session, email="owner4@example.com", password="owner-password-1", role="user")
    client.post(
        "/api/v1/auth/login", json={"email": "owner4@example.com", "password": "owner-password-1"}
    )
    project = _create_project(client)
    client.post(
        f"/api/v1/projects/{project['id']}/secrets",
        json={"name": "demo_password", "value": "hunter2", "kind": "password"},
    )
    client.post("/api/v1/auth/logout")

    make_user(db_session, email="other4@example.com", password="other-password-1", role="user")
    client.post(
        "/api/v1/auth/login", json={"email": "other4@example.com", "password": "other-password-1"}
    )
    resp = client.get(f"/api/v1/projects/{project['id']}/secrets")
    assert resp.status_code == 403
