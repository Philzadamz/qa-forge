"""Built-in deterministic routines for default scenarios (PRD §7.6.1 "Deterministic
defaults"): no LLM call, just Playwright driving a known login/logout flow.

A default test case opts in by carrying one of `ROUTINES`' keys as a tag (set by the admin on
`default_test_cases.tags` — reuses the existing field rather than adding a new "Automatable"
column/admin UI, which is out of scope for this phase). Routines are written against
`infra/demo-target`'s markup (`#username`, `#password`, the login form's single submit
button, `#welcome`) since that's the only target with a known, stable shape; running one
against an arbitrary project URL is future work (PRD's ADM-DC-7 admin-configurable
selectors), not implemented here.
"""

from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.enums import TestStatus
from app.services.execution.tools import BrowserTools, ToolError

SecretLookup = Callable[[str], str]


@dataclass
class DeterministicResult:
    status: TestStatus
    actual_result: str
    log: list[str] = field(default_factory=list)


RoutineFn = Callable[[BrowserTools, str, SecretLookup], DeterministicResult]


def _routine_login_valid(
    tools: BrowserTools, target_url: str, resolve_secret: SecretLookup
) -> DeterministicResult:
    log: list[str] = []
    log.append(tools.navigate(target_url))
    try:
        password = resolve_secret("demo_password")
    except KeyError:
        password = "Demo12345!"  # noqa: S105 - infra/demo-target's own known default, not a real secret
    log.append(tools.fill("#username", "demo"))
    log.append(tools.fill("#password", password))
    log.append(tools.click("button[type=submit]"))
    try:
        log.append(tools.wait_for(ref="#welcome", timeout_ms=5000))
    except ToolError:
        return DeterministicResult(
            status=TestStatus.FAILED,
            actual_result="Did not reach the dashboard after submitting valid credentials.",
            log=log,
        )
    return DeterministicResult(
        status=TestStatus.PASSED, actual_result="Logged in successfully.", log=log
    )


def _routine_login_invalid(
    tools: BrowserTools, target_url: str, resolve_secret: SecretLookup
) -> DeterministicResult:
    log = [
        tools.navigate(target_url),
        tools.fill("#username", "demo"),
        tools.fill("#password", "wrong-password"),
        tools.click("button[type=submit]"),
    ]
    try:
        log.append(tools.wait_for(text="Invalid username or password", timeout_ms=5000))
    except ToolError:
        return DeterministicResult(
            status=TestStatus.FAILED,
            actual_result="No invalid-credentials error was shown for a wrong password.",
            log=log,
        )
    return DeterministicResult(
        status=TestStatus.PASSED,
        actual_result="Invalid credentials were rejected with an error.",
        log=log,
    )


def _routine_blank_fields(
    tools: BrowserTools, target_url: str, resolve_secret: SecretLookup
) -> DeterministicResult:
    log = [tools.navigate(target_url), tools.click("button[type=submit]")]
    try:
        log.append(tools.wait_for(text="required", timeout_ms=5000))
    except ToolError:
        return DeterministicResult(
            status=TestStatus.FAILED,
            actual_result="Submitting blank credentials did not show a validation error.",
            log=log,
        )
    return DeterministicResult(
        status=TestStatus.PASSED,
        actual_result="Blank submission was rejected with a validation error.",
        log=log,
    )


def _routine_logout(
    tools: BrowserTools, target_url: str, resolve_secret: SecretLookup
) -> DeterministicResult:
    login = _routine_login_valid(tools, target_url, resolve_secret)
    log = list(login.log)
    if login.status != TestStatus.PASSED:
        return DeterministicResult(
            status=TestStatus.BLOCKED, actual_result="Could not log in to test logout.", log=log
        )
    log.append(tools.click("button[type=submit]"))  # the dashboard's only button is "Log out"
    try:
        log.append(tools.wait_for(ref="#username", timeout_ms=5000))
    except ToolError:
        return DeterministicResult(
            status=TestStatus.FAILED,
            actual_result="Logout did not return to the login page.",
            log=log,
        )
    log.append(tools.back())
    try:
        tools.wait_for(ref="#welcome", timeout_ms=3000)
        return DeterministicResult(
            status=TestStatus.FAILED,
            actual_result="Pressing Back after logout re-displayed the dashboard (no cache "
            "invalidation on logout).",
            log=log,
        )
    except ToolError:
        return DeterministicResult(
            status=TestStatus.PASSED,
            actual_result="Logged out and the Back button did not restore the dashboard.",
            log=log,
        )


def _routine_security_headers(
    tools: BrowserTools, target_url: str, resolve_secret: SecretLookup
) -> DeterministicResult:
    import httpx

    response = httpx.get(target_url, follow_redirects=True)
    log = [f"GET {target_url} -> {response.status_code}"]
    required = ["x-content-type-options", "x-frame-options", "content-security-policy"]
    present = {k.lower() for k in response.headers}
    missing = [h for h in required if h not in present]
    if missing:
        return DeterministicResult(
            status=TestStatus.FAILED,
            actual_result=f"Missing security headers: {', '.join(missing)}.",
            log=log,
        )
    return DeterministicResult(
        status=TestStatus.PASSED,
        actual_result="All expected security headers were present.",
        log=log,
    )


ROUTINES: dict[str, RoutineFn] = {
    "deterministic:login_valid": _routine_login_valid,
    "deterministic:login_invalid": _routine_login_invalid,
    "deterministic:blank_fields": _routine_blank_fields,
    "deterministic:logout_back_button": _routine_logout,
    "deterministic:security_headers": _routine_security_headers,
}


def routine_for_tags(tags: list[str]) -> RoutineFn | None:
    for tag in tags:
        if tag in ROUTINES:
            return ROUTINES[tag]
    return None
