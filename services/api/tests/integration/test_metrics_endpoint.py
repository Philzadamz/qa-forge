from fastapi.testclient import TestClient


def test_metrics_endpoint_exposes_prometheus_text(client: TestClient) -> None:
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "qaforge_ai_tokens_total" in resp.text
    assert "qaforge_run_duration_seconds" in resp.text
