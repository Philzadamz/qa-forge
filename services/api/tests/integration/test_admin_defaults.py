from io import BytesIO

from fastapi.testclient import TestClient
from openpyxl import Workbook


def _create_type(admin_client: TestClient, name: str = "Web Application") -> str:
    resp = admin_client.post("/api/v1/admin/types", json={"name": name})
    return str(resp.json()["id"])


def test_create_update_delete_default(admin_client: TestClient) -> None:
    type_id = _create_type(admin_client)

    created = admin_client.post(
        f"/api/v1/admin/types/{type_id}/defaults",
        json={
            "feature": "Login",
            "scenario": "Check that valid login succeeds",
            "steps": ["Open the app", "Log in"],
            "expected_result": "User is logged in",
        },
    ).json()
    assert created["version"] == 1

    updated = admin_client.patch(
        f"/api/v1/admin/defaults/{created['id']}", json={"scenario": "Updated scenario"}
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["scenario"] == "Updated scenario"

    deleted = admin_client.delete(f"/api/v1/admin/defaults/{created['id']}")
    assert deleted.status_code == 204

    listing = admin_client.get(f"/api/v1/admin/types/{type_id}/defaults")
    assert listing.json() == []


def test_reorder_defaults(admin_client: TestClient) -> None:
    type_id = _create_type(admin_client)
    ids = []
    for feature in ("Login", "Logout", "2FA"):
        created = admin_client.post(
            f"/api/v1/admin/types/{type_id}/defaults",
            json={
                "feature": feature,
                "scenario": f"Check {feature}",
                "steps": ["Step 1"],
                "expected_result": "Expected",
            },
        ).json()
        ids.append(created["id"])

    new_order = list(reversed(ids))
    resp = admin_client.post(
        f"/api/v1/admin/types/{type_id}/defaults/reorder", json={"ordered_ids": new_order}
    )
    assert resp.status_code == 200
    assert [c["id"] for c in resp.json()] == new_order


def test_reorder_rejects_mismatched_ids(admin_client: TestClient) -> None:
    type_id = _create_type(admin_client)
    admin_client.post(
        f"/api/v1/admin/types/{type_id}/defaults",
        json={"feature": "Login", "scenario": "Check", "steps": ["Step"], "expected_result": "E"},
    )

    resp = admin_client.post(
        f"/api/v1/admin/types/{type_id}/defaults/reorder",
        json={"ordered_ids": ["00000000-0000-0000-0000-000000000000"]},
    )
    assert resp.status_code == 400


def _build_template_workbook() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Test Case"
    ws.append(
        (
            "TESTCASE NO",
            "FEATURE",
            "OPERATIONS / SCENERIOS",
            "STEPS TO EXECUTE",
            "EXPECTED RESULT",
            "ACTUAL RESULT",
            "STATUS",
            "EVIDENCE",
        )
    )
    ws.append(("DEFAULT SCENARIOS", None, None, None, None, None, None, None))
    ws.append(
        (
            "P_001",
            "Login",
            "Check that valid credentials grant access",
            "1. Open the app.\n2. Log in.",
            "User is logged in",
            "As expected",
            "Passed",
            None,
        )
    )
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def test_import_preview_does_not_save(admin_client: TestClient) -> None:
    type_id = _create_type(admin_client)
    data = _build_template_workbook()

    resp = admin_client.post(
        f"/api/v1/admin/types/{type_id}/defaults/import",
        files={
            "file": (
                "defaults.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["cases"]) == 1
    assert body["cases"][0]["feature"] == "Login"

    listing = admin_client.get(f"/api/v1/admin/types/{type_id}/defaults")
    assert listing.json() == []


def test_import_confirm_saves_cases(admin_client: TestClient) -> None:
    type_id = _create_type(admin_client)
    data = _build_template_workbook()
    preview = admin_client.post(
        f"/api/v1/admin/types/{type_id}/defaults/import",
        files={
            "file": (
                "defaults.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()

    resp = admin_client.post(
        f"/api/v1/admin/types/{type_id}/defaults/import/confirm",
        json={"cases": preview["cases"], "replace_existing": False},
    )
    assert resp.status_code == 201
    assert len(resp.json()) == 1

    listing = admin_client.get(f"/api/v1/admin/types/{type_id}/defaults")
    assert len(listing.json()) == 1


def test_export_returns_csv(admin_client: TestClient) -> None:
    type_id = _create_type(admin_client)
    admin_client.post(
        f"/api/v1/admin/types/{type_id}/defaults",
        json={
            "feature": "Login",
            "scenario": "Check login",
            "steps": ["Step 1"],
            "expected_result": "E",
        },
    )

    resp = admin_client.get(f"/api/v1/admin/types/{type_id}/defaults/export")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "Login" in resp.text
