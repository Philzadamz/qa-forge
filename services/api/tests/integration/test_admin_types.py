from fastapi.testclient import TestClient


def test_create_and_list_types(admin_client: TestClient) -> None:
    resp = admin_client.post(
        "/api/v1/admin/types",
        json={"name": "Web Application", "description": "Web QA", "sort_order": 1},
    )
    assert resp.status_code == 201
    created = resp.json()
    assert created["name"] == "Web Application"
    assert created["is_active"] is True

    listing = admin_client.get("/api/v1/admin/types")
    assert listing.status_code == 200
    assert any(t["id"] == created["id"] for t in listing.json())


def test_create_duplicate_name_rejected(admin_client: TestClient) -> None:
    admin_client.post("/api/v1/admin/types", json={"name": "Web Application"})
    resp = admin_client.post("/api/v1/admin/types", json={"name": "Web Application"})
    assert resp.status_code == 409


def test_deactivate_type_keeps_it_but_hides_from_users(admin_client: TestClient) -> None:
    created = admin_client.post("/api/v1/admin/types", json={"name": "API"}).json()

    patched = admin_client.patch(f"/api/v1/admin/types/{created['id']}", json={"is_active": False})
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False

    still_there = admin_client.get(f"/api/v1/admin/types/{created['id']}")
    assert still_there.status_code == 200


def test_delete_type_with_defaults_is_blocked(admin_client: TestClient) -> None:
    created = admin_client.post("/api/v1/admin/types", json={"name": "Mobile"}).json()
    admin_client.post(
        f"/api/v1/admin/types/{created['id']}/defaults",
        json={
            "feature": "Login",
            "scenario": "Check login",
            "steps": ["Open app", "Log in"],
            "expected_result": "Logged in",
        },
    )

    resp = admin_client.delete(f"/api/v1/admin/types/{created['id']}")
    assert resp.status_code == 409


def test_delete_type_without_defaults_succeeds(admin_client: TestClient) -> None:
    created = admin_client.post("/api/v1/admin/types", json={"name": "Empty Type"}).json()
    resp = admin_client.delete(f"/api/v1/admin/types/{created['id']}")
    assert resp.status_code == 204


def test_duplicate_type_copies_defaults(admin_client: TestClient) -> None:
    created = admin_client.post("/api/v1/admin/types", json={"name": "Web Application"}).json()
    admin_client.post(
        f"/api/v1/admin/types/{created['id']}/defaults",
        json={
            "feature": "Login",
            "scenario": "Check login",
            "steps": ["Open app", "Log in"],
            "expected_result": "Logged in",
        },
    )

    resp = admin_client.post(f"/api/v1/admin/types/{created['id']}/duplicate")
    assert resp.status_code == 201
    clone = resp.json()
    assert clone["name"] == "Web Application (copy)"

    clone_defaults = admin_client.get(f"/api/v1/admin/types/{clone['id']}/defaults")
    assert len(clone_defaults.json()) == 1
