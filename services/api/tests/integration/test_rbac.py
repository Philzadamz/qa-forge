"""Every admin endpoint must reject anonymous (401) and non-admin (403) callers."""

import pytest
from fastapi.testclient import TestClient

ADMIN_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/v1/admin/types"),
    ("POST", "/api/v1/admin/types"),
    ("GET", "/api/v1/admin/types/00000000-0000-0000-0000-000000000000"),
    ("PATCH", "/api/v1/admin/types/00000000-0000-0000-0000-000000000000"),
    ("DELETE", "/api/v1/admin/types/00000000-0000-0000-0000-000000000000"),
    ("POST", "/api/v1/admin/types/00000000-0000-0000-0000-000000000000/duplicate"),
    ("GET", "/api/v1/admin/types/00000000-0000-0000-0000-000000000000/defaults"),
    ("POST", "/api/v1/admin/types/00000000-0000-0000-0000-000000000000/defaults"),
    ("PATCH", "/api/v1/admin/defaults/00000000-0000-0000-0000-000000000000"),
    ("DELETE", "/api/v1/admin/defaults/00000000-0000-0000-0000-000000000000"),
    ("POST", "/api/v1/admin/types/00000000-0000-0000-0000-000000000000/defaults/reorder"),
    ("POST", "/api/v1/admin/types/00000000-0000-0000-0000-000000000000/defaults/import/confirm"),
    ("GET", "/api/v1/admin/types/00000000-0000-0000-0000-000000000000/defaults/export"),
    ("GET", "/api/v1/admin/users"),
    ("POST", "/api/v1/admin/users"),
    ("GET", "/api/v1/admin/users/00000000-0000-0000-0000-000000000000"),
    ("PATCH", "/api/v1/admin/users/00000000-0000-0000-0000-000000000000"),
    ("POST", "/api/v1/admin/users/00000000-0000-0000-0000-000000000000/reset-password"),
    ("GET", "/api/v1/admin/templates"),
    ("POST", "/api/v1/admin/templates/00000000-0000-0000-0000-000000000000/activate"),
    ("POST", "/api/v1/admin/templates/00000000-0000-0000-0000-000000000000/archive"),
    ("GET", "/api/v1/admin/templates/00000000-0000-0000-0000-000000000000/preview"),
    ("DELETE", "/api/v1/admin/templates/00000000-0000-0000-0000-000000000000"),
    ("GET", "/api/v1/admin/report-defaults"),
    ("PUT", "/api/v1/admin/report-defaults"),
    ("GET", "/api/v1/admin/snippets"),
    ("POST", "/api/v1/admin/snippets"),
    ("PATCH", "/api/v1/admin/snippets/00000000-0000-0000-0000-000000000000"),
    ("DELETE", "/api/v1/admin/snippets/00000000-0000-0000-0000-000000000000"),
]


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
def test_admin_endpoint_rejects_anonymous(client: TestClient, method: str, path: str) -> None:
    resp = client.request(method, path, json={} if method in ("POST", "PATCH") else None)
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"


@pytest.mark.parametrize("method,path", ADMIN_ENDPOINTS)
def test_admin_endpoint_rejects_non_admin(user_client: TestClient, method: str, path: str) -> None:
    resp = user_client.request(method, path, json={} if method in ("POST", "PATCH") else None)
    assert resp.status_code == 403, f"{method} {path} -> {resp.status_code}"
