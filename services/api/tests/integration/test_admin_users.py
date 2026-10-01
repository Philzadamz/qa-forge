from fastapi.testclient import TestClient


def test_create_user(admin_client: TestClient) -> None:
    resp = admin_client.post(
        "/api/v1/admin/users",
        json={
            "email": "new.user@example.com",
            "full_name": "New User",
            "role": "user",
            "password": "a-strong-password",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "new.user@example.com"
    assert "password" not in body
    assert "password_hash" not in body


def test_create_duplicate_email_rejected(admin_client: TestClient) -> None:
    payload = {
        "email": "dup@example.com",
        "full_name": "Dup",
        "role": "user",
        "password": "a-strong-password",
    }
    admin_client.post("/api/v1/admin/users", json=payload)
    resp = admin_client.post("/api/v1/admin/users", json=payload)
    assert resp.status_code == 409


def test_deactivate_user(admin_client: TestClient) -> None:
    created = admin_client.post(
        "/api/v1/admin/users",
        json={
            "email": "to.deactivate@example.com",
            "full_name": "Bye",
            "role": "user",
            "password": "a-strong-password",
        },
    ).json()

    resp = admin_client.patch(f"/api/v1/admin/users/{created['id']}", json={"is_active": False})
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_admin_cannot_deactivate_self(admin_client: TestClient) -> None:
    me = admin_client.get("/api/v1/auth/me").json()
    resp = admin_client.patch(f"/api/v1/admin/users/{me['id']}", json={"is_active": False})
    assert resp.status_code == 400


def test_reset_user_password(admin_client: TestClient) -> None:
    created = admin_client.post(
        "/api/v1/admin/users",
        json={
            "email": "reset.me@example.com",
            "full_name": "Reset",
            "role": "user",
            "password": "original-password",
        },
    ).json()

    resp = admin_client.post(
        f"/api/v1/admin/users/{created['id']}/reset-password",
        json={"new_password": "brand-new-password"},
    )
    assert resp.status_code == 204

    login = admin_client.post(
        "/api/v1/auth/login",
        json={"email": "reset.me@example.com", "password": "brand-new-password"},
    )
    assert login.status_code == 200
