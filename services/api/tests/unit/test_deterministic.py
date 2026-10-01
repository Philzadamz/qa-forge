import httpx
import pytest

from app.core.enums import TestStatus
from app.services.execution.deterministic import ROUTINES, routine_for_tags
from tests.unit.fake_browser_tools import FakeBrowserTools


def test_routine_for_tags_matches_known_tag() -> None:
    routine = routine_for_tags(["some-other-tag", "deterministic:login_valid"])
    assert routine is ROUTINES["deterministic:login_valid"]


def test_routine_for_tags_returns_none_when_no_match() -> None:
    assert routine_for_tags(["unrelated", "also-unrelated"]) is None


def test_login_valid_passes_when_dashboard_is_reached() -> None:
    tools = FakeBrowserTools()
    result = ROUTINES["deterministic:login_valid"](tools, "http://x", lambda name: "secret-value")
    assert result.status == TestStatus.PASSED
    assert [c[0] for c in tools.calls] == ["navigate", "fill", "fill", "click", "wait_for"]


def test_login_valid_falls_back_to_demo_default_when_secret_missing() -> None:
    tools = FakeBrowserTools()

    def resolve(name: str) -> str:
        raise KeyError(name)

    ROUTINES["deterministic:login_valid"](tools, "http://x", resolve)
    fill_calls = [c for c in tools.calls if c[0] == "fill"]
    assert fill_calls[1][1]["value"] == "Demo12345!"


def test_login_valid_fails_when_dashboard_not_reached() -> None:
    tools = FakeBrowserTools(wait_for_fails={"#welcome"})
    result = ROUTINES["deterministic:login_valid"](tools, "http://x", lambda name: "x")
    assert result.status == TestStatus.FAILED


def test_login_invalid_passes_when_error_shown() -> None:
    tools = FakeBrowserTools()
    result = ROUTINES["deterministic:login_invalid"](tools, "http://x", lambda name: "x")
    assert result.status == TestStatus.PASSED


def test_login_invalid_fails_when_no_error_shown() -> None:
    tools = FakeBrowserTools(wait_for_fails={"Invalid username or password"})
    result = ROUTINES["deterministic:login_invalid"](tools, "http://x", lambda name: "x")
    assert result.status == TestStatus.FAILED


def test_blank_fields_passes_when_validation_error_shown() -> None:
    tools = FakeBrowserTools()
    result = ROUTINES["deterministic:blank_fields"](tools, "http://x", lambda name: "x")
    assert result.status == TestStatus.PASSED


class _WelcomeOnlyOnceTools(FakeBrowserTools):
    """`#welcome` is reachable the first time (after login) but not the second (after the
    Back button, post-logout) — the shape a real "logout invalidates cached pages" pass needs."""

    def __init__(self) -> None:
        super().__init__()
        self._welcome_wait_count = 0

    def wait_for(
        self, *, text: str | None = None, ref: str | None = None, timeout_ms: int = 5000
    ) -> str:
        if ref == "#welcome":
            self._welcome_wait_count += 1
            if self._welcome_wait_count > 1:
                from app.services.execution.tools import ToolError

                self.calls.append(("wait_for", {"text": text, "ref": ref}))
                raise ToolError("Timed out waiting for '#welcome'")
        return super().wait_for(text=text, ref=ref, timeout_ms=timeout_ms)


def test_logout_passes_when_back_does_not_restore_dashboard() -> None:
    tools = _WelcomeOnlyOnceTools()
    result = ROUTINES["deterministic:logout_back_button"](tools, "http://x", lambda name: "x")
    assert result.status == TestStatus.PASSED


def test_logout_fails_when_back_restores_dashboard() -> None:
    tools = FakeBrowserTools()  # #welcome is always reachable -> Back restores the dashboard
    result = ROUTINES["deterministic:logout_back_button"](tools, "http://x", lambda name: "x")
    assert result.status == TestStatus.FAILED


def test_security_headers_passes_when_all_present(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, follow_redirects: bool = True) -> httpx.Response:
        return httpx.Response(
            200,
            headers={
                "x-content-type-options": "nosniff",
                "x-frame-options": "DENY",
                "content-security-policy": "default-src 'self'",
            },
            request=httpx.Request("GET", url),
        )

    monkeypatch.setattr(httpx, "get", fake_get)
    result = ROUTINES["deterministic:security_headers"](
        FakeBrowserTools(), "http://x", lambda n: "x"
    )
    assert result.status == TestStatus.PASSED


def test_security_headers_fails_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_get(url: str, follow_redirects: bool = True) -> httpx.Response:
        return httpx.Response(200, headers={}, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)
    result = ROUTINES["deterministic:security_headers"](
        FakeBrowserTools(), "http://x", lambda n: "x"
    )
    assert result.status == TestStatus.FAILED
    assert "x-content-type-options" in result.actual_result
