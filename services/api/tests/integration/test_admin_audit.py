from fastapi.testclient import TestClient


def test_non_admin_cannot_read_audit_log(user_client: TestClient) -> None:
    resp = user_client.get("/api/v1/admin/audit-log")
    assert resp.status_code == 403


def test_admin_sees_recorded_login_events(admin_client: TestClient) -> None:
    resp = admin_client.get("/api/v1/admin/audit-log", params={"action": "login"})
    assert resp.status_code == 200
    rows = resp.json()
    assert rows, "the admin's own login should be recorded"
    assert all(row["action"] == "login" for row in rows)


def test_audit_log_filters_by_entity(admin_client: TestClient) -> None:
    admin_client.post(
        "/api/v1/admin/users",
        json={
            "email": "newbie@example.com",
            "full_name": "Newbie",
            "role": "user",
            "password": "password-123",
        },
    )
    resp = admin_client.get("/api/v1/admin/audit-log", params={"entity": "user"})
    assert resp.status_code == 200
    assert all(row["entity"] == "user" for row in resp.json())


def test_audit_log_rejects_out_of_range_limit(admin_client: TestClient) -> None:
    resp = admin_client.get("/api/v1/admin/audit-log", params={"limit": 0})
    assert resp.status_code == 422
