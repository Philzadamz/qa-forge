import io
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook
from PIL import Image

from tests.golden.fixtures_paths import needs_xlsx_template


def _create_project(client: TestClient) -> dict:
    return client.post(
        "/api/v1/projects", json={"name": "Kusala", "app_code": "KUSALA", "id_prefix": "Kusala"}
    ).json()


def _create_type_with_one_default(admin_client: TestClient) -> dict:
    type_obj = admin_client.post("/api/v1/admin/types", json={"name": "Web Application"}).json()
    admin_client.post(
        f"/api/v1/admin/types/{type_obj['id']}/defaults",
        json={
            "feature": "Login",
            "scenario": "Check login",
            "steps": ["Log in."],
            "expected_result": "Logged in",
        },
    )
    return type_obj


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (100, 50), color=(1, 2, 3)).save(buf, format="PNG")
    return buf.getvalue()


def test_upload_and_list_evidence(admin_client: TestClient) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type_with_one_default(admin_client)
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": {"project_name_line": "X"},
        },
    ).json()
    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]

    resp = admin_client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        files={"file": ("screenshot.png", _png_bytes(), "image/png")},
    )
    assert resp.status_code == 201, resp.text
    evidence = resp.json()
    assert evidence["caption"] == "screenshot.png"

    listing = admin_client.get(f"/api/v1/cases/{case['id']}/evidence").json()
    assert len(listing) == 1


def test_upload_evidence_rejects_bad_content_type(admin_client: TestClient) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type_with_one_default(admin_client)
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": {"project_name_line": "X"},
        },
    ).json()
    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]

    resp = admin_client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        files={"file": ("payload.exe", b"not an image", "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_get_evidence_file_returns_the_image_bytes(admin_client: TestClient) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type_with_one_default(admin_client)
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": {"project_name_line": "X"},
        },
    ).json()
    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]
    png = _png_bytes()
    evidence = admin_client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        files={"file": ("a.png", png, "image/png")},
    ).json()

    resp = admin_client.get(f"/api/v1/evidence/{evidence['id']}/file")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "image/png"
    assert resp.content == png


def test_delete_evidence(admin_client: TestClient) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type_with_one_default(admin_client)
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": {"project_name_line": "X"},
        },
    ).json()
    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]
    evidence = admin_client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        files={"file": ("a.png", _png_bytes(), "image/png")},
    ).json()

    resp = admin_client.delete(f"/api/v1/evidence/{evidence['id']}")
    assert resp.status_code == 204

    listing = admin_client.get(f"/api/v1/cases/{case['id']}/evidence").json()
    assert listing == []


@needs_xlsx_template
def test_evidence_in_xlsx_export(admin_client: TestClient, tmp_path: Path) -> None:
    project = _create_project(admin_client)
    type_obj = _create_type_with_one_default(admin_client)
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "Evidence Suite",
            "header": {"project_name_line": "KUSALA: Evidence Suite"},
        },
    ).json()
    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]
    admin_client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        files={"file": ("proof.png", _png_bytes(), "image/png")},
    )

    resp = admin_client.post(f"/api/v1/suites/{suite['id']}/export/xlsx")
    assert resp.status_code == 200
    out = tmp_path / "out.xlsx"
    out.write_bytes(resp.content)
    wb = load_workbook(out)
    ws = wb["Test Case"]
    assert ws["H13"].value == "'Default Scenarios'!A1"
    assert "Default Scenarios" in wb.sheetnames
    assert len(wb["Default Scenarios"]._images) == 1


def _case_for_upload(admin_client: TestClient) -> dict:
    project = _create_project(admin_client)
    type_obj = _create_type_with_one_default(admin_client)
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": {"project_name_line": "X"},
        },
    ).json()
    return admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]


def test_evidence_rejects_text_spoofed_as_png(admin_client: TestClient) -> None:
    case = _case_for_upload(admin_client)
    resp = admin_client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        files={"file": ("looks-fine.png", b"<script>alert(1)</script>", "image/png")},
    )
    assert resp.status_code == 400


def test_evidence_stores_sniffed_extension_not_the_client_filename(
    admin_client: TestClient,
) -> None:
    case = _case_for_upload(admin_client)
    resp = admin_client.post(
        f"/api/v1/cases/{case['id']}/evidence",
        files={"file": ("shot.html", _png_bytes(), "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    download = admin_client.get(f"/api/v1/evidence/{resp.json()['id']}/file")
    assert download.status_code == 200
    assert download.headers["content-type"] == "image/png"
