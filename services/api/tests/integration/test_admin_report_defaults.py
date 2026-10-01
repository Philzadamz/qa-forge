from fastapi.testclient import TestClient


def test_get_report_defaults_creates_singleton_on_first_access(admin_client: TestClient) -> None:
    resp = admin_client.get("/api/v1/admin/report-defaults")
    assert resp.status_code == 200
    body = resp.json()
    assert body["classification_label"] == "Public"
    assert body["exit_criteria"] == []


def test_update_report_defaults(admin_client: TestClient) -> None:
    resp = admin_client.put(
        "/api/v1/admin/report-defaults",
        json={
            "exit_criteria": ["All cases executed"],
            "approval_roles": [{"action": "Tested By", "default_name": "", "default_staff_id": ""}],
            "classification_label": "Internal",
            "organisation_name": "Sterling Bank",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["exit_criteria"] == ["All cases executed"]
    assert body["classification_label"] == "Internal"

    # GET again returns the same singleton row, not a new one.
    again = admin_client.get("/api/v1/admin/report-defaults").json()
    assert again["id"] == body["id"]


def test_snippet_crud(admin_client: TestClient) -> None:
    created = admin_client.post(
        "/api/v1/admin/snippets",
        json={"title": "Config-driven note", "body": "This is configuration-driven."},
    )
    assert created.status_code == 201
    snippet = created.json()
    assert snippet["is_active"] is True

    listing = admin_client.get("/api/v1/admin/snippets").json()
    assert any(s["id"] == snippet["id"] for s in listing)

    patched = admin_client.patch(
        f"/api/v1/admin/snippets/{snippet['id']}", json={"is_active": False}
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    deleted = admin_client.delete(f"/api/v1/admin/snippets/{snippet['id']}")
    assert deleted.status_code == 204
