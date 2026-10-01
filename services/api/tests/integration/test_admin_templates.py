from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

from tests.golden.fixtures_paths import DOCX_TEMPLATE as REAL_DOCX_TEMPLATE
from tests.golden.fixtures_paths import XLSX_TEMPLATE as REAL_XLSX_TEMPLATE


def _broken_xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Not The Right Sheet"
    ws["A1"] = "nonsense"
    buffer = BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


@pytest.mark.skipif(not REAL_XLSX_TEMPLATE.exists(), reason="real xlsx template not present")
def test_upload_valid_xlsx_template_is_immediately_usable(admin_client: TestClient) -> None:
    resp = admin_client.post(
        "/api/v1/admin/templates",
        params={"kind": "xlsx_test_cases", "name": "Default xlsx"},
        files={
            "file": (
                "QA_Test_Cases_Template.xlsx",
                REAL_XLSX_TEMPLATE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "xlsx_test_cases"
    assert body["validation_error"] is None
    assert body["status"] == "draft"
    assert body["is_default"] is False


def test_upload_broken_xlsx_template_records_validation_error(admin_client: TestClient) -> None:
    resp = admin_client.post(
        "/api/v1/admin/templates",
        params={"kind": "xlsx_test_cases", "name": "Broken xlsx"},
        files={
            "file": (
                "broken.xlsx",
                _broken_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["validation_error"] is not None


def test_cannot_activate_invalid_template(admin_client: TestClient) -> None:
    created = admin_client.post(
        "/api/v1/admin/templates",
        params={"kind": "xlsx_test_cases", "name": "Broken xlsx"},
        files={
            "file": (
                "broken.xlsx",
                _broken_xlsx_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()

    resp = admin_client.post(f"/api/v1/admin/templates/{created['id']}/activate")
    assert resp.status_code == 400


@pytest.mark.skipif(not REAL_XLSX_TEMPLATE.exists(), reason="real xlsx template not present")
def test_activate_sets_default_and_unsets_previous(admin_client: TestClient) -> None:
    def upload(name: str) -> dict:
        return admin_client.post(
            "/api/v1/admin/templates",
            params={"kind": "xlsx_test_cases", "name": name},
            files={
                "file": (
                    "t.xlsx",
                    REAL_XLSX_TEMPLATE.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
        ).json()

    first = upload("v1")
    second = upload("v2")

    activate_first = admin_client.post(f"/api/v1/admin/templates/{first['id']}/activate")
    assert activate_first.status_code == 200
    assert activate_first.json()["is_default"] is True

    activate_second = admin_client.post(f"/api/v1/admin/templates/{second['id']}/activate")
    assert activate_second.status_code == 200

    listing = admin_client.get("/api/v1/admin/templates", params={"kind": "xlsx_test_cases"}).json()
    defaults = [t for t in listing if t["is_default"]]
    assert len(defaults) == 1
    assert defaults[0]["id"] == second["id"]


@pytest.mark.skipif(not REAL_XLSX_TEMPLATE.exists(), reason="real xlsx template not present")
def test_preview_returns_rendered_file(admin_client: TestClient) -> None:
    created = admin_client.post(
        "/api/v1/admin/templates",
        params={"kind": "xlsx_test_cases", "name": "Preview me"},
        files={
            "file": (
                "t.xlsx",
                REAL_XLSX_TEMPLATE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()

    resp = admin_client.get(f"/api/v1/admin/templates/{created['id']}/preview")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert len(resp.content) > 0


@pytest.mark.skipif(not REAL_XLSX_TEMPLATE.exists(), reason="real xlsx template not present")
def test_cannot_delete_default_template(admin_client: TestClient) -> None:
    created = admin_client.post(
        "/api/v1/admin/templates",
        params={"kind": "xlsx_test_cases", "name": "Undeletable"},
        files={
            "file": (
                "t.xlsx",
                REAL_XLSX_TEMPLATE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    ).json()
    admin_client.post(f"/api/v1/admin/templates/{created['id']}/activate")

    resp = admin_client.delete(f"/api/v1/admin/templates/{created['id']}")
    assert resp.status_code == 409


@pytest.mark.skipif(not REAL_DOCX_TEMPLATE.exists(), reason="real docx template not present")
def test_upload_valid_docx_template_is_tokenized_and_usable(admin_client: TestClient) -> None:
    resp = admin_client.post(
        "/api/v1/admin/templates",
        params={"kind": "docx_report", "name": "Default docx"},
        files={
            "file": (
                "QA_Test_Report_Template.docx",
                REAL_DOCX_TEMPLATE.read_bytes(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            )
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["validation_error"] is None

    preview = admin_client.get(f"/api/v1/admin/templates/{body['id']}/preview")
    assert preview.status_code == 200
    assert preview.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
