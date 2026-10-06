from fastapi.testclient import TestClient


def test_openapi_url_import_rejects_internal_addresses(user_client: TestClient) -> None:
    resp = user_client.post(
        "/api/v1/api-specs/parse",
        data={"kind": "openapi", "url": "http://169.254.169.254/latest/meta-data/"},
    )
    assert resp.status_code == 400
    assert "non-public" in resp.text


def test_openapi_url_import_rejects_loopback(user_client: TestClient) -> None:
    resp = user_client.post(
        "/api/v1/api-specs/parse",
        data={"kind": "openapi", "url": "http://127.0.0.1:8000/api/v1/admin/users"},
    )
    assert resp.status_code == 400
