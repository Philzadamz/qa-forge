import io
import uuid
import zipfile

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.services.ai.client import FakeLLMClient
from tests.golden.fixtures_paths import needs_docx_template


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (120, 40), color=(10, 20, 200)).save(buf, format="PNG")
    return buf.getvalue()


def _draft_report(admin_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> dict:
    project = admin_client.post(
        "/api/v1/projects", json={"name": "Sig", "app_code": "SIG", "id_prefix": "Sig"}
    ).json()
    type_obj = admin_client.post(
        "/api/v1/admin/types", json={"name": f"Sig type {uuid.uuid4()}"}
    ).json()
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": {"project_name_line": "SIG: S"},
        },
    ).json()
    monkeypatch.setattr(
        "app.routers.reports.build_llm_client", lambda settings: FakeLLMClient(responses=["{}"])
    )
    return admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft").json()


def test_upload_fetch_and_remove_signature(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _draft_report(admin_client, monkeypatch)
    url = f"/api/v1/reports/{report['id']}/approvals/0/signature"

    uploaded = admin_client.post(url, files={"file": ("sig.png", _png_bytes(), "image/png")})
    assert uploaded.status_code == 200, uploaded.text
    key = uploaded.json()["fields_json"]["approvals"][0]["signature_key"]
    assert key and key.endswith(".png")

    fetched = admin_client.get(url)
    assert fetched.status_code == 200
    assert fetched.headers["content-type"] == "image/png"
    assert fetched.content == _png_bytes()

    removed = admin_client.delete(url)
    assert removed.status_code == 200
    assert removed.json()["fields_json"]["approvals"][0]["signature_key"] is None
    assert admin_client.get(url).status_code == 404


def test_replacing_a_signature_keeps_only_the_latest(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _draft_report(admin_client, monkeypatch)
    url = f"/api/v1/reports/{report['id']}/approvals/1/signature"
    first = admin_client.post(url, files={"file": ("a.png", _png_bytes(), "image/png")}).json()
    second = admin_client.post(url, files={"file": ("b.png", _png_bytes(), "image/png")}).json()
    assert (
        first["fields_json"]["approvals"][1]["signature_key"]
        != second["fields_json"]["approvals"][1]["signature_key"]
    )


def test_signature_upload_rejects_non_images_and_bad_rows(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _draft_report(admin_client, monkeypatch)
    url = f"/api/v1/reports/{report['id']}/approvals/0/signature"
    spoofed = admin_client.post(
        url, files={"file": ("sig.png", b"<html>not an image</html>", "image/png")}
    )
    assert spoofed.status_code == 400
    missing_row = admin_client.post(
        f"/api/v1/reports/{report['id']}/approvals/99/signature",
        files={"file": ("sig.png", _png_bytes(), "image/png")},
    )
    assert missing_row.status_code == 404


@needs_docx_template
def test_rendered_report_embeds_the_signature_image(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    report = _draft_report(admin_client, monkeypatch)
    admin_client.post(
        f"/api/v1/reports/{report['id']}/approvals/0/signature",
        files={"file": ("sig.png", _png_bytes(), "image/png")},
    )
    rendered = admin_client.post(f"/api/v1/reports/{report['id']}/render?format=docx")
    assert rendered.status_code == 200, rendered.text
    names = zipfile.ZipFile(io.BytesIO(rendered.content)).namelist()
    assert any(n.startswith("word/media/") for n in names)
