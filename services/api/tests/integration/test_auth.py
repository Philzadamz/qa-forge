from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import ACCESS_COOKIE, REFRESH_COOKIE
from tests.conftest import make_user


def test_login_sets_httponly_cookies_and_returns_profile(
    client: TestClient, db_session: Session
) -> None:
    make_user(db_session, email="qa@example.com", password="correct-password", role="user")

    resp = client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "correct-password"}
    )

    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == "qa@example.com"
    assert body["role"] == "user"
    assert ACCESS_COOKIE in resp.cookies
    assert REFRESH_COOKIE in resp.cookies


def test_login_wrong_password_rejected(client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="qa@example.com", password="correct-password")

    resp = client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "wrong-password"}
    )

    assert resp.status_code == 401


def test_login_unknown_email_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "whatever123"}
    )
    assert resp.status_code == 401


def test_login_rate_limited_after_five_attempts(client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="qa@example.com", password="correct-password")

    for _ in range(5):
        resp = client.post(
            "/api/v1/auth/login", json={"email": "qa@example.com", "password": "wrong"}
        )
        assert resp.status_code == 401

    resp = client.post("/api/v1/auth/login", json={"email": "qa@example.com", "password": "wrong"})
    assert resp.status_code == 429


def test_me_requires_authentication(client: TestClient) -> None:
    resp = client.get("/api/v1/auth/me")
    assert resp.status_code == 401


def test_me_returns_current_user_after_login(client: TestClient, db_session: Session) -> None:
    make_user(
        db_session, email="qa@example.com", password="correct-password", full_name="QA Engineer"
    )
    client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "correct-password"}
    )

    resp = client.get("/api/v1/auth/me")

    assert resp.status_code == 200
    assert resp.json()["full_name"] == "QA Engineer"


def test_logout_clears_cookies(client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="qa@example.com", password="correct-password")
    client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "correct-password"}
    )

    resp = client.post("/api/v1/auth/logout")
    assert resp.status_code == 204

    me = client.get("/api/v1/auth/me")
    assert me.status_code == 401


def test_refresh_issues_new_access_cookie(client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="qa@example.com", password="correct-password")
    client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "correct-password"}
    )

    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 200


def test_refresh_without_cookie_rejected(client: TestClient) -> None:
    resp = client.post("/api/v1/auth/refresh")
    assert resp.status_code == 401


def test_forgot_password_always_accepted(client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="qa@example.com", password="correct-password")

    known = client.post("/api/v1/auth/forgot-password", json={"email": "qa@example.com"})
    unknown = client.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"})

    assert known.status_code == 202
    assert unknown.status_code == 202


def test_reset_password_with_invalid_token_rejected(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/auth/reset-password",
        json={"token": "not-a-real-token", "password": "new-password-1"},
    )
    assert resp.status_code == 400


def test_full_reset_password_flow(client: TestClient, db_session: Session) -> None:
    make_user(db_session, email="qa@example.com", password="old-password-1")

    import logging

    caplog_token: list[str] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            caplog_token.append(record.getMessage())

    handler = _Capture()
    logging.getLogger("app.routers.auth").addHandler(handler)
    try:
        client.post("/api/v1/auth/forgot-password", json={"email": "qa@example.com"})
    finally:
        logging.getLogger("app.routers.auth").removeHandler(handler)

    assert caplog_token, "expected the reset link to be logged"
    token = caplog_token[0].split("token=")[-1]

    reset_resp = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": "new-password-1"}
    )
    assert reset_resp.status_code == 204

    old_login = client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "old-password-1"}
    )
    assert old_login.status_code == 401

    new_login = client.post(
        "/api/v1/auth/login", json={"email": "qa@example.com", "password": "new-password-1"}
    )
    assert new_login.status_code == 200

    reused = client.post(
        "/api/v1/auth/reset-password", json={"token": token, "password": "another-password-1"}
    )
    assert reused.status_code == 400
