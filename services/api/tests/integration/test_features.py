import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from tests.conftest import make_user


def _set(admin_client: TestClient, key: str, enabled: bool) -> None:
    resp = admin_client.put(f"/api/v1/admin/features/{key}", json={"enabled": enabled})
    assert resp.status_code == 200, resp.text


def _suite_with_case(admin_client: TestClient) -> tuple[dict, dict]:
    project = admin_client.post(
        "/api/v1/projects", json={"name": "Flags", "app_code": "FLG", "id_prefix": "Flg"}
    ).json()
    type_obj = admin_client.post(
        "/api/v1/admin/types", json={"name": f"Flag type {uuid.uuid4()}"}
    ).json()
    admin_client.post(
        f"/api/v1/admin/types/{type_obj['id']}/defaults",
        json={
            "feature": "Login",
            "scenario": "Check login",
            "steps": ["Log in."],
            "expected_result": "Logged in",
        },
    )
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "S",
            "header": {"project_name_line": "FLG: S"},
        },
    ).json()
    case = admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()[0]
    return suite, case


def test_every_feature_is_on_by_default(user_client: TestClient) -> None:
    features = user_client.get("/api/v1/features").json()
    assert {f["key"] for f in features} >= {
        "test_lab_web",
        "test_lab_api",
        "test_lab_android",
        "api_spec_import",
        "ai_case_generation",
        "report_generation",
        "bug_tracking",
    }
    assert all(f["enabled"] for f in features)


def test_non_admin_cannot_change_features(user_client: TestClient) -> None:
    resp = user_client.put("/api/v1/admin/features/bug_tracking", json={"enabled": False})
    assert resp.status_code == 403
    assert user_client.get("/api/v1/admin/features").status_code == 403


def test_unknown_feature_key_is_rejected(admin_client: TestClient) -> None:
    resp = admin_client.put("/api/v1/admin/features/not_a_feature", json={"enabled": False})
    assert resp.status_code == 404


def test_toggle_is_recorded_in_the_audit_log(admin_client: TestClient, db_session: Session) -> None:
    _set(admin_client, "report_generation", False)
    entry = (
        db_session.query(AuditLog)
        .filter(AuditLog.entity == "feature_flag", AuditLog.entity_id == "report_generation")
        .one()
    )
    assert entry.diff == {"enabled": {"from": True, "to": False}}


def test_disabled_android_blocks_apk_routes_and_android_runs(
    admin_client: TestClient, db_session: Session
) -> None:
    suite, case = _suite_with_case(admin_client)
    project_id = suite["project_id"]
    _set(admin_client, "test_lab_android", False)

    assert admin_client.get(f"/api/v1/projects/{project_id}/apks").status_code == 403
    run = admin_client.post(
        "/api/v1/runs",
        json={"suite_id": suite["id"], "case_ids": [case["id"]], "target": "android"},
    )
    assert run.status_code == 403
    assert "turned off" in run.text

    _set(admin_client, "test_lab_android", True)
    assert admin_client.get(f"/api/v1/projects/{project_id}/apks").status_code == 200


def test_disabled_web_runs_are_refused_but_other_targets_still_work(
    admin_client: TestClient,
) -> None:
    suite, case = _suite_with_case(admin_client)
    _set(admin_client, "test_lab_web", False)
    refused = admin_client.post(
        "/api/v1/runs",
        json={"suite_id": suite["id"], "case_ids": [case["id"]], "target": "web"},
    )
    assert refused.status_code == 403
    allowed = admin_client.post(
        "/api/v1/runs",
        json={"suite_id": suite["id"], "case_ids": [case["id"]], "target": "api"},
    )
    assert allowed.status_code != 403


def test_disabled_api_spec_import_refuses_spec_parsing(admin_client: TestClient) -> None:
    _set(admin_client, "api_spec_import", False)
    resp = admin_client.post(
        "/api/v1/api-specs/parse", data={"kind": "curl", "curl_text": "curl https://x.test"}
    )
    assert resp.status_code == 403


def test_disabled_reports_block_drafting(admin_client: TestClient) -> None:
    suite, _ = _suite_with_case(admin_client)
    _set(admin_client, "report_generation", False)
    assert admin_client.post(f"/api/v1/suites/{suite['id']}/reports/draft").status_code == 403


def test_disabled_ai_generation_blocks_case_generation(admin_client: TestClient) -> None:
    suite, _ = _suite_with_case(admin_client)
    _set(admin_client, "ai_case_generation", False)
    resp = admin_client.post(f"/api/v1/suites/{suite['id']}/generate", json={"story_ids": []})
    assert resp.status_code == 403


def test_disabled_bug_tracking_blocks_bug_listing(admin_client: TestClient) -> None:
    suite, _ = _suite_with_case(admin_client)
    _set(admin_client, "bug_tracking", False)
    assert admin_client.get(f"/api/v1/suites/{suite['id']}/bugs").status_code == 403


def test_flag_state_is_visible_to_signed_in_users(
    admin_client: TestClient, client: TestClient, db_session: Session
) -> None:
    _set(admin_client, "bug_tracking", False)
    make_user(db_session, email="viewer-check@example.com", password="viewer-password-1")
    client.post(
        "/api/v1/auth/login",
        json={"email": "viewer-check@example.com", "password": "viewer-password-1"},
    )
    flags = {f["key"]: f["enabled"] for f in client.get("/api/v1/features").json()}
    assert flags["bug_tracking"] is False
