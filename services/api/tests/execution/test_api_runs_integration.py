"""End-to-end API-target Test Lab run against the real `infra/demo-api` fixture: spec
parsing, AI case generation (FakeLLMClient), execution (real httpx against a real server),
apply-to-suite, and evidence (both the PNG render and the text log)."""

import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from app.services.ai.client import FakeLLMClient


def _wait_for_run(client: TestClient, run_id: str, *, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/runs/{run_id}").json()
        if run["status"] not in ("queued", "running"):
            return run
        time.sleep(0.1)
    raise AssertionError(f"Run {run_id} did not finish within {timeout}s")


def _setup_suite(admin_client: TestClient, demo_api_url: str) -> tuple[dict, dict]:
    project = admin_client.post(
        "/api/v1/projects",
        json={
            "name": "Demo API QA",
            "app_code": "DEMOAPI",
            "id_prefix": "DemoAPI",
            "default_test_url": demo_api_url,
        },
    ).json()
    type_obj = admin_client.post("/api/v1/admin/types", json={"name": "API"}).json()
    suite = admin_client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_obj["id"],
            "name": "Transfers API Suite",
            "header": {"project_name_line": "DEMOAPI: Transfers"},
        },
    ).json()
    return project, suite


def test_parse_live_openapi_spec_from_demo_api(admin_client: TestClient, demo_api_url: str) -> None:
    resp = admin_client.post(
        "/api/v1/api-specs/parse",
        data={"kind": "openapi", "url": f"{demo_api_url}/openapi.json"},
    )
    assert resp.status_code == 200, resp.text
    catalogue = resp.json()
    paths = {(e["method"], e["path"]) for e in catalogue["endpoints"]}
    assert ("POST", "/transfers") in paths
    assert ("GET", "/transfers/{transfer_id}") in paths


def test_generate_api_cases_with_fake_llm(
    admin_client: TestClient, monkeypatch: pytest.MonkeyPatch, demo_api_url: str
) -> None:
    _, suite = _setup_suite(admin_client, demo_api_url)

    draft_json = json.dumps(
        {
            "cases": [
                {
                    "feature": "POST /transfers",
                    "scenario": "Check that a valid transfer is created",
                    "steps": ["Send a valid transfer request."],
                    "expected_result": "201 with the created transfer.",
                    "category": "happy_path",
                    "priority": "P1",
                    "request_plan": {
                        "method": "POST",
                        "path": "/transfers",
                        "headers": {"Authorization": "Bearer {{secret_demo_token}}"},
                        "body": {"account_id": "acc-1", "amount": 100, "reference": "ref-1"},
                        "extract": {"transfer_id": "id"},
                        "assertions": [{"kind": "status_equals", "expected": 201}],
                    },
                }
            ]
        }
    )
    fake_client = FakeLLMClient(responses=[draft_json])
    monkeypatch.setattr("app.routers.api_lab.build_llm_client", lambda settings: fake_client)

    resp = admin_client.post(
        f"/api/v1/suites/{suite['id']}/generate-api-cases",
        json={
            "suite_id": suite["id"],
            "endpoints": [{"method": "POST", "path": "/transfers", "summary": "Create a transfer"}],
            "guidance": "Focus on the happy path first.",
        },
    )
    assert resp.status_code == 200, resp.text
    cases = resp.json()
    assert len(cases) == 1
    assert cases[0]["feature"] == "POST /transfers"
    assert cases[0]["display_id"]


def test_full_api_run_execute_apply_and_evidence(
    admin_client: TestClient, demo_api_url: str
) -> None:
    project, suite = _setup_suite(admin_client, demo_api_url)

    admin_client.post(
        f"/api/v1/projects/{project['id']}/secrets",
        json={"name": "demo_token", "value": "demo-token-a", "kind": "token"},
    )

    create_case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "POST /transfers",
            "scenario": "Check that a valid transfer is created",
            "steps": ["Send a valid transfer."],
            "expected_result": "201 Created.",
        },
    ).json()
    admin_client.patch(
        f"/api/v1/cases/{create_case['id']}",
        json={
            "request_plan": {
                "method": "POST",
                "path": "/transfers",
                "headers": {"Authorization": "Bearer {{secret_demo_token}}"},
                "body": {"account_id": "acc-1", "amount": 100, "reference": "ref-e2e-1"},
                "extract": {"transfer_id": "id"},
                "assertions": [{"kind": "status_equals", "expected": 201}],
            }
        },
    )

    get_case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "GET /transfers/{id}",
            "scenario": "Check that the created transfer can be fetched back",
            "steps": ["Fetch the transfer created by the previous case."],
            "expected_result": "200 with the matching transfer id.",
        },
    ).json()
    admin_client.patch(
        f"/api/v1/cases/{get_case['id']}",
        json={
            "request_plan": {
                "method": "GET",
                "path": "/transfers/{{transfer_id}}",
                "headers": {"Authorization": "Bearer {{secret_demo_token}}"},
                "assertions": [
                    {"kind": "status_equals", "expected": 200},
                    {"kind": "json_path_equals", "path": "id", "expected": "{{transfer_id}}"},
                ],
            }
        },
    )

    unauthorized_case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "POST /transfers",
            "scenario": "Check that a missing Authorization header is rejected",
            "steps": ["Send a transfer request with no Authorization header."],
            "expected_result": "401 Unauthorized.",
        },
    ).json()
    admin_client.patch(
        f"/api/v1/cases/{unauthorized_case['id']}",
        json={
            "request_plan": {
                "method": "POST",
                "path": "/transfers",
                "body": {"account_id": "acc-1", "amount": 1, "reference": "ref-e2e-2"},
                "assertions": [{"kind": "status_equals", "expected": 401}],
            }
        },
    )

    created = admin_client.post(
        "/api/v1/runs",
        json={
            "suite_id": suite["id"],
            "target": "api",
            "case_ids": [create_case["id"], get_case["id"], unauthorized_case["id"]],
        },
    ).json()
    assert created["status"] == "queued"
    run = _wait_for_run(admin_client, created["id"])
    assert run["status"] == "passed", run

    results = run["summary_json"]["cases"]
    assert results[create_case["id"]]["status"] == "Passed"
    assert results[get_case["id"]]["status"] == "Passed"
    assert results[unauthorized_case["id"]]["status"] == "Passed"  # correctly asserted the 401
    assert all(r["mode"] == "api" for r in results.values())

    # Review-before-apply still holds for the API target.
    cases_before = {
        c["id"]: c for c in admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    }
    assert cases_before[create_case["id"]]["status"] == "Not Tested"

    applied = admin_client.post(f"/api/v1/runs/{run['id']}/apply", json={}).json()
    assert all(r["applied"] for r in applied["summary_json"]["cases"].values())

    cases_after = {
        c["id"]: c for c in admin_client.get(f"/api/v1/suites/{suite['id']}/cases").json()
    }
    assert cases_after[create_case["id"]]["status"] == "Passed"
    assert cases_after[create_case["id"]]["execution_mode"] == "automated"

    evidence = admin_client.get(f"/api/v1/cases/{create_case['id']}/evidence").json()
    assert len(evidence) == 2  # one PNG render, one text log
    kinds = {e["id"]: e["caption"] for e in evidence}
    file_resp = admin_client.get(f"/api/v1/evidence/{evidence[0]['id']}/file")
    assert file_resp.status_code == 200

    # The secret value never leaked into any evidence file.
    for e in evidence:
        body = admin_client.get(f"/api/v1/evidence/{e['id']}/file").content
        assert b"demo-token-a" not in body
    assert kinds  # sanity: captions were set


def test_postman_and_pytest_export(admin_client: TestClient, demo_api_url: str) -> None:
    _, suite = _setup_suite(admin_client, demo_api_url)
    case = admin_client.post(
        f"/api/v1/suites/{suite['id']}/cases",
        json={
            "section": "functional",
            "feature": "POST /transfers",
            "scenario": "Check that a valid transfer is created",
            "steps": ["Send a valid transfer."],
            "expected_result": "201 Created.",
        },
    ).json()
    admin_client.patch(
        f"/api/v1/cases/{case['id']}",
        json={
            "request_plan": {
                "method": "POST",
                "path": "/transfers",
                "body": {"account_id": "acc-1", "amount": 100, "reference": "ref-export"},
                "assertions": [{"kind": "status_equals", "expected": 201}],
            }
        },
    )

    postman = admin_client.get(f"/api/v1/suites/{suite['id']}/export/postman")
    assert postman.status_code == 200
    collection = postman.json()
    assert collection["item"][0]["request"]["method"] == "POST"

    pytest_file = admin_client.get(f"/api/v1/suites/{suite['id']}/export/pytest")
    assert pytest_file.status_code == 200
    assert "def test_" in pytest_file.text
    assert "httpx.request" in pytest_file.text


def test_demo_api_itself_behaves_as_expected(demo_api_url: str) -> None:
    """Smoke-checks the fixture app directly (not through QA Forge) so a failure here points
    straight at the fixture, not at the runner."""
    r = httpx.post(
        f"{demo_api_url}/transfers",
        headers={"Authorization": "Bearer demo-token-a"},
        json={"account_id": "a1", "amount": 100, "reference": "smoke-1"},
    )
    assert r.status_code == 201
    transfer_id = r.json()["id"]

    # Idempotent replay: same reference returns the same transfer, not a new one.
    r2 = httpx.post(
        f"{demo_api_url}/transfers",
        headers={"Authorization": "Bearer demo-token-a"},
        json={"account_id": "a1", "amount": 999, "reference": "smoke-1"},
    )
    assert r2.json()["id"] == transfer_id

    # IDOR: user b cannot read user a's transfer.
    r3 = httpx.get(
        f"{demo_api_url}/transfers/{transfer_id}", headers={"Authorization": "Bearer demo-token-b"}
    )
    assert r3.status_code == 403

    # Over the limit.
    r4 = httpx.post(
        f"{demo_api_url}/transfers",
        headers={"Authorization": "Bearer demo-token-a"},
        json={"account_id": "a1", "amount": 999_999, "reference": "smoke-2"},
    )
    assert r4.status_code == 400
