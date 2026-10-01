import httpx

from app.core.enums import TestStatus
from app.services.execution.api_models import AssertionSpec, RequestPlan
from app.services.execution.api_runner import execute_request_plan


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_status_equals_assertion_passes() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "abc"})

    plan = RequestPlan(
        method="POST",
        path="/transfers",
        assertions=[AssertionSpec(kind="status_equals", expected=201)],
    )
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.status == TestStatus.PASSED


def test_status_equals_assertion_fails() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    plan = RequestPlan(
        method="GET",
        path="/transfers",
        assertions=[AssertionSpec(kind="status_equals", expected=200)],
    )
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.status == TestStatus.FAILED
    assert "status 500" in result.actual_result


def test_json_path_equals() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "completed", "nested": {"id": "x1"}})

    plan = RequestPlan(
        method="GET",
        path="/transfers/1",
        assertions=[
            AssertionSpec(kind="json_path_equals", path="status", expected="completed"),
            AssertionSpec(kind="json_path_equals", path="nested.id", expected="x1"),
        ],
    )
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.status == TestStatus.PASSED


def test_json_path_contains() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"items": [1, 2, 3]})

    plan = RequestPlan(
        method="GET",
        path="/transfers",
        assertions=[AssertionSpec(kind="json_path_contains", path="items", expected=2)],
    )
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.status == TestStatus.PASSED


def test_schema_valid_assertion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "abc", "amount": 100})

    schema = {
        "type": "object",
        "required": ["id", "amount"],
        "properties": {"id": {"type": "string"}, "amount": {"type": "number"}},
    }
    plan = RequestPlan(
        method="GET",
        path="/transfers/1",
        assertions=[AssertionSpec(kind="schema_valid", expected=schema)],
    )
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.status == TestStatus.PASSED


def test_schema_valid_assertion_fails_on_mismatch() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": 123})  # id should be a string

    schema = {"type": "object", "properties": {"id": {"type": "string"}}}
    plan = RequestPlan(
        method="GET", path="/x", assertions=[AssertionSpec(kind="schema_valid", expected=schema)]
    )
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.status == TestStatus.FAILED


def test_header_present_assertion() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"x-request-id": "r1"})

    plan = RequestPlan(
        method="GET",
        path="/x",
        assertions=[AssertionSpec(kind="header_present", path="x-request-id")],
    )
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.status == TestStatus.PASSED


def test_extracted_variables_are_returned() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(201, json={"id": "transfer-42"})

    plan = RequestPlan(method="POST", path="/transfers", extract={"transfer_id": "id"})
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.extracted == {"transfer_id": "transfer-42"}


def test_var_substitution_in_assertion_expected_value() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "abc123"})

    plan = RequestPlan(
        method="GET",
        path="/x",
        assertions=[AssertionSpec(kind="json_path_equals", path="id", expected="{{created_id}}")],
    )
    result = execute_request_plan(
        plan,
        base_url="http://x",
        client=_client(handler),
        context={"created_id": "abc123"},
        secret_values=[],
    )
    assert result.status == TestStatus.PASSED


def test_var_substitution_in_path_and_headers() -> None:
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["path"] = request.url.path
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={})

    plan = RequestPlan(
        method="GET",
        path="/transfers/{{transfer_id}}",
        headers={"Authorization": "Bearer {{token}}"},
    )
    execute_request_plan(
        plan,
        base_url="http://x",
        client=_client(handler),
        context={"transfer_id": "abc123", "token": "secret-tok"},
        secret_values=[],
    )
    assert seen["path"] == "/transfers/abc123"
    assert seen["auth"] == "Bearer secret-tok"


def test_secret_values_are_masked_in_the_log() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    plan = RequestPlan(
        method="GET", path="/x", headers={"Authorization": "Bearer top-secret-value"}
    )
    result = execute_request_plan(
        plan,
        base_url="http://x",
        client=_client(handler),
        context={},
        secret_values=["top-secret-value"],
    )
    assert "top-secret-value" not in result.log_text
    assert "[MASKED_SECRET_1]" in result.log_text


def test_request_failure_is_reported_as_failed_not_an_exception() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    plan = RequestPlan(method="GET", path="/x")
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.status == TestStatus.FAILED
    assert "connection refused" in result.actual_result


def test_log_image_is_a_valid_png() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"ok": True})

    plan = RequestPlan(method="GET", path="/x")
    result = execute_request_plan(
        plan, base_url="http://x", client=_client(handler), context={}, secret_values=[]
    )
    assert result.log_image[:8] == b"\x89PNG\r\n\x1a\n"
