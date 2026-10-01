"""APK upload validation that doesn't need a real emulator — just `aapt` and the fixture
file. Full upload-and-run-against-a-real-device coverage lives in
tests/execution/test_android_runs_integration.py."""

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.conftest import make_user

REPO_ROOT = Path(__file__).resolve().parents[4]
SAMPLE_APK = REPO_ROOT / "infra" / "demo-android" / "ApiDemos-debug.apk"

needs_sample_apk = pytest.mark.skipif(
    not SAMPLE_APK.exists(), reason="infra/demo-android/ApiDemos-debug.apk not present"
)


def _create_project(client: TestClient) -> dict:
    resp = client.post(
        "/api/v1/projects", json={"name": "Kusala", "app_code": "KUSALA", "id_prefix": "Kusala"}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_upload_rejects_non_apk_extension(user_client: TestClient) -> None:
    project = _create_project(user_client)
    resp = user_client.post(
        f"/api/v1/projects/{project['id']}/apks",
        files={"file": ("not-an-apk.txt", io.BytesIO(b"hello"), "text/plain")},
    )
    assert resp.status_code == 400
    assert "apk" in resp.text.lower()


def test_upload_rejects_a_corrupt_apk(user_client: TestClient) -> None:
    project = _create_project(user_client)
    resp = user_client.post(
        f"/api/v1/projects/{project['id']}/apks",
        files={
            "file": ("broken.apk", io.BytesIO(b"not a real zip/apk"), "application/octet-stream")
        },
    )
    assert resp.status_code == 400


@needs_sample_apk
def test_upload_and_list_and_delete(user_client: TestClient) -> None:
    project = _create_project(user_client)
    with open(SAMPLE_APK, "rb") as f:
        resp = user_client.post(
            f"/api/v1/projects/{project['id']}/apks",
            files={"file": ("ApiDemos-debug.apk", f, "application/vnd.android.package-archive")},
        )
    assert resp.status_code == 201, resp.text
    apk = resp.json()
    assert apk["package_name"] == "io.appium.android.apis"

    listed = user_client.get(f"/api/v1/projects/{project['id']}/apks").json()
    assert len(listed) == 1

    delete_resp = user_client.delete(f"/api/v1/apks/{apk['id']}")
    assert delete_resp.status_code == 204
    assert user_client.get(f"/api/v1/projects/{project['id']}/apks").json() == []


@needs_sample_apk
def test_user_cannot_upload_to_another_users_project(
    client: TestClient, db_session: Session
) -> None:
    make_user(db_session, email="apkowner@example.com", password="owner-password-1", role="user")
    client.post(
        "/api/v1/auth/login", json={"email": "apkowner@example.com", "password": "owner-password-1"}
    )
    project = _create_project(client)
    client.post("/api/v1/auth/logout")

    make_user(db_session, email="apkother@example.com", password="other-password-1", role="user")
    client.post(
        "/api/v1/auth/login", json={"email": "apkother@example.com", "password": "other-password-1"}
    )
    with open(SAMPLE_APK, "rb") as f:
        resp = client.post(
            f"/api/v1/projects/{project['id']}/apks",
            files={"file": ("ApiDemos-debug.apk", f, "application/vnd.android.package-archive")},
        )
    assert resp.status_code == 403
