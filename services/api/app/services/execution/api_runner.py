"""Executes a compiled `RequestPlan` with httpx (PRD §7.6.2 steps 3-5): no LLM involved —
once an API test case has a request plan, running it is always deterministic, unlike Web's
agent-vs-script split. Supports chained flows via `{{var}}` substitution from earlier
responses' `extract`ed values, and renders a masked request/response log to a PNG for the
xlsx evidence sheet (PRD: "rendered as an image ... and stored as text" — the text lives in
the `RunStep.message`/`input_masked` columns already written for every other runner; the PNG
is the one new artifact this module produces).
"""

import json
import re
import time
from dataclasses import dataclass

import httpx
import jsonschema

from app.core.enums import TestStatus
from app.services.ai.masking import mask_secrets, mask_text
from app.services.execution.api_models import AssertionSpec, RequestPlan
from app.services.execution.log_image import render_text_to_png

_VAR_RE = re.compile(r"\{\{(\w+)\}\}")


class ApiRunnerError(Exception):
    pass


@dataclass
class ApiStepResult:
    status: TestStatus
    actual_result: str
    log_text: str
    log_image: bytes
    duration_ms: int
    extracted: dict[str, str]


def _substitute(value: str, context: dict[str, str]) -> str:
    return _VAR_RE.sub(lambda m: context.get(m.group(1), m.group(0)), value)


def _substitute_deep(value: object, context: dict[str, str]) -> object:
    if isinstance(value, str):
        return _substitute(value, context)
    if isinstance(value, dict):
        return {k: _substitute_deep(v, context) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_deep(v, context) for v in value]
    return value


def _json_path_get(data: object, path: str) -> object:
    """Dot-path lookup, e.g. "id" or "items.0.id" — no wildcards or filters, deliberately
    minimal (PRD gives no JSONPath library requirement; this covers the assertions the AI is
    prompted to generate)."""
    current = data
    for part in path.split("."):
        if isinstance(current, list):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _evaluate_assertion(
    assertion: AssertionSpec, *, response: httpx.Response, duration_ms: int
) -> tuple[bool, str]:
    if assertion.kind == "status_equals":
        ok = response.status_code == int(str(assertion.expected))
        return ok, f"status {response.status_code} == {assertion.expected}"
    if assertion.kind == "header_present":
        ok = bool(assertion.path) and assertion.path in response.headers
        return ok, f"header {assertion.path!r} present"
    if assertion.kind == "latency_below_ms":
        threshold = float(str(assertion.expected))
        ok = duration_ms < threshold
        return ok, f"latency {duration_ms}ms < {threshold}ms"

    try:
        body = response.json()
    except (json.JSONDecodeError, ValueError):
        return False, "response body was not valid JSON"

    if assertion.kind == "schema_valid":
        if not isinstance(assertion.expected, dict):
            return False, "schema_valid needs a JSON Schema object in `expected`"
        try:
            jsonschema.validate(body, assertion.expected)
            return True, "response matches the expected schema"
        except jsonschema.ValidationError as exc:
            return False, f"schema mismatch: {exc.message}"
        except jsonschema.SchemaError as exc:
            return False, f"invalid schema given for schema_valid: {exc}"

    value = _json_path_get(body, assertion.path or "")
    if assertion.kind == "json_path_equals":
        ok = value == assertion.expected
        return ok, f"{assertion.path} == {assertion.expected!r} (got {value!r})"
    if assertion.kind == "json_path_contains":
        try:
            ok = assertion.expected in value if value is not None else False  # type: ignore[operator]
        except TypeError:
            ok = False
        return ok, f"{assertion.path} contains {assertion.expected!r} (got {value!r})"
    if assertion.kind == "json_path_matches":
        ok = bool(re.search(str(assertion.expected), str(value)))
        return ok, f"{assertion.path} matches {assertion.expected!r} (got {value!r})"
    return False, f"unknown assertion kind {assertion.kind!r}"


def execute_request_plan(
    plan: RequestPlan,
    *,
    base_url: str,
    client: httpx.Client,
    context: dict[str, str],
    secret_values: list[str],
) -> ApiStepResult:
    url = base_url.rstrip("/") + _substitute(plan.path, context)
    headers = {k: _substitute(v, context) for k, v in plan.headers.items()}
    query = {k: _substitute(v, context) for k, v in plan.query.items()}
    body = _substitute_deep(plan.body, context) if plan.body is not None else None

    started = time.monotonic()
    try:
        response = client.request(
            plan.method, url, headers=headers, params=query, json=body, timeout=10.0
        )
    except httpx.HTTPError as exc:
        duration_ms = int((time.monotonic() - started) * 1000)
        log_text = f"{plan.method} {url}\n\nRequest failed: {exc}"
        masked = mask_secrets(mask_text(log_text).text, secret_values).text
        return ApiStepResult(
            status=TestStatus.FAILED,
            actual_result=f"Request failed: {exc}",
            log_text=masked,
            log_image=render_text_to_png(masked),
            duration_ms=duration_ms,
            extracted={},
        )
    duration_ms = int((time.monotonic() - started) * 1000)

    # `expected` needs the same `{{var}}` substitution as the request itself — otherwise a
    # chained assertion like "the fetched id equals the id the create step extracted" can
    # never pass, since it would compare against the literal, unsubstituted "{{var}}" string.
    substituted_assertions = [
        a.model_copy(update={"expected": _substitute_deep(a.expected, context)})
        for a in plan.assertions
    ]
    results = [
        _evaluate_assertion(a, response=response, duration_ms=duration_ms)
        for a in substituted_assertions
    ]
    passed = all(ok for ok, _ in results)

    extracted: dict[str, str] = {}
    try:
        response_json = response.json()
        for var_name, path in plan.extract.items():
            value = _json_path_get(response_json, path)
            if value is not None:
                extracted[var_name] = str(value)
    except (json.JSONDecodeError, ValueError):
        pass

    body_preview = response.text[:2000]
    log_text = (
        f"{plan.method} {url}\n"
        f"Request headers: {headers}\n"
        f"Request body: {json.dumps(body) if body is not None else '(none)'}\n\n"
        f"Response: {response.status_code} ({duration_ms}ms)\n"
        f"Response headers: {dict(response.headers)}\n"
        f"Response body: {body_preview}\n\n"
        "Assertions:\n" + "\n".join(f"  {'PASS' if ok else 'FAIL'} - {msg}" for ok, msg in results)
    )
    masked = mask_secrets(mask_text(log_text).text, secret_values).text[:50_000]

    actual_result = (
        "All assertions passed." if passed else "; ".join(msg for ok, msg in results if not ok)
    )
    return ApiStepResult(
        status=TestStatus.PASSED if passed else TestStatus.FAILED,
        actual_result=actual_result,
        log_text=masked,
        log_image=render_text_to_png(masked),
        duration_ms=duration_ms,
        extracted=extracted,
    )
