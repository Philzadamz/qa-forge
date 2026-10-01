"""Every workspace endpoint must reject anonymous callers (401)."""

import pytest
from fastapi.testclient import TestClient

ZERO = "00000000-0000-0000-0000-000000000000"

WORKSPACE_ENDPOINTS: list[tuple[str, str]] = [
    ("GET", "/api/v1/types"),
    ("GET", f"/api/v1/types/{ZERO}/defaults"),
    ("GET", "/api/v1/projects"),
    ("POST", "/api/v1/projects"),
    ("GET", f"/api/v1/projects/{ZERO}"),
    ("PATCH", f"/api/v1/projects/{ZERO}"),
    ("DELETE", f"/api/v1/projects/{ZERO}"),
    ("GET", f"/api/v1/projects/{ZERO}/stories"),
    ("POST", f"/api/v1/projects/{ZERO}/stories/paste"),
    ("GET", f"/api/v1/stories/{ZERO}"),
    ("GET", f"/api/v1/projects/{ZERO}/suites"),
    ("POST", "/api/v1/suites"),
    ("GET", f"/api/v1/suites/{ZERO}"),
    ("PATCH", f"/api/v1/suites/{ZERO}"),
    ("POST", f"/api/v1/suites/{ZERO}/refresh-defaults"),
    ("POST", f"/api/v1/suites/{ZERO}/generate"),
    ("GET", f"/api/v1/jobs/{ZERO}"),
    ("POST", f"/api/v1/suites/{ZERO}/cycles"),
    ("GET", f"/api/v1/suites/{ZERO}/cases"),
    ("POST", f"/api/v1/suites/{ZERO}/cases"),
    ("POST", f"/api/v1/suites/{ZERO}/cases/bulk"),
    ("PATCH", f"/api/v1/cases/{ZERO}"),
    ("DELETE", f"/api/v1/cases/{ZERO}"),
    ("POST", f"/api/v1/suites/{ZERO}/export/xlsx"),
    ("GET", f"/api/v1/cases/{ZERO}/evidence"),
    ("GET", f"/api/v1/evidence/{ZERO}/file"),
    ("DELETE", f"/api/v1/evidence/{ZERO}"),
    ("GET", f"/api/v1/suites/{ZERO}/bugs"),
    ("POST", f"/api/v1/suites/{ZERO}/bugs"),
    ("POST", f"/api/v1/cases/{ZERO}/bugs/draft"),
    ("PATCH", f"/api/v1/bugs/{ZERO}"),
    ("DELETE", f"/api/v1/bugs/{ZERO}"),
    ("GET", f"/api/v1/suites/{ZERO}/reports"),
    ("POST", f"/api/v1/suites/{ZERO}/reports/draft"),
    ("GET", f"/api/v1/reports/{ZERO}"),
    ("PUT", f"/api/v1/reports/{ZERO}"),
    ("POST", f"/api/v1/reports/{ZERO}/render"),
]


@pytest.mark.parametrize("method,path", WORKSPACE_ENDPOINTS)
def test_workspace_endpoint_rejects_anonymous(client: TestClient, method: str, path: str) -> None:
    resp = client.request(method, path, json={} if method in ("POST", "PATCH") else None)
    assert resp.status_code == 401, f"{method} {path} -> {resp.status_code}"
