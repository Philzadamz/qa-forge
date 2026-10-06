from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.rate_limit import reset as reset_rate_limit
from app.core.security import hash_password
from app.db.session import get_engine, get_sessionmaker
from app.models import Base
from app.models.user import User


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setenv("AI_PROVIDER", "fake")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    monkeypatch.setenv("STORAGE_LOCAL_ROOT", str(tmp_path / "storage"))
    monkeypatch.setenv("JWT_SECRET", "test-secret-key-at-least-32-bytes-long")
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()

    Base.metadata.create_all(get_engine())
    reset_rate_limit()
    yield
    get_engine().dispose()
    for cached in (get_settings, get_engine, get_sessionmaker):
        cached.cache_clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    from app.main import create_app

    with TestClient(create_app()) as c:
        yield c


@pytest.fixture
def db_session() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.close()


def make_user(
    db_session: Session,
    *,
    email: str,
    password: str = "correct horse battery",
    role: str = "user",
    full_name: str = "Test User",
) -> User:
    user = User(email=email, full_name=full_name, role=role, password_hash=hash_password(password))
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_client(client: TestClient, db_session: Session) -> TestClient:
    make_user(db_session, email="admin@example.com", password="admin-password-1", role="admin")
    resp = client.post(
        "/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password-1"}
    )
    assert resp.status_code == 200, resp.text
    return client


@pytest.fixture
def user_client(client: TestClient, db_session: Session) -> TestClient:
    make_user(db_session, email="user@example.com", password="user-password-1", role="user")
    resp = client.post(
        "/api/v1/auth/login", json={"email": "user@example.com", "password": "user-password-1"}
    )
    assert resp.status_code == 200, resp.text
    return client
