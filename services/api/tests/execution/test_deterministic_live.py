"""Deterministic default routines (PRD §7.6.1) run against the real `infra/demo-target` app
through a real headless Chromium page — the unit tests (fake tools) prove the routine logic;
this proves the CSS selectors in `deterministic.py` actually match demo-target's real markup."""

from app.core.enums import TestStatus
from app.services.execution.deterministic import ROUTINES
from app.services.execution.tools import BrowserTools


def _resolve_secret(name: str) -> str:
    raise KeyError(name)  # forces the routine's demo-default fallback ("Demo12345!")


def test_login_valid_live(demo_target_url: str, page) -> None:
    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    result = ROUTINES["deterministic:login_valid"](
        tools, f"{demo_target_url}/login", _resolve_secret
    )
    assert result.status == TestStatus.PASSED


def test_login_invalid_live(demo_target_url: str, page) -> None:
    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    result = ROUTINES["deterministic:login_invalid"](
        tools, f"{demo_target_url}/login", _resolve_secret
    )
    assert result.status == TestStatus.PASSED


def test_blank_fields_live(demo_target_url: str, page) -> None:
    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    result = ROUTINES["deterministic:blank_fields"](
        tools, f"{demo_target_url}/login", _resolve_secret
    )
    assert result.status == TestStatus.PASSED


def test_logout_back_button_live(demo_target_url: str, page) -> None:
    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    result = ROUTINES["deterministic:logout_back_button"](
        tools, f"{demo_target_url}/login", _resolve_secret
    )
    assert result.status == TestStatus.PASSED


def test_security_headers_live(demo_target_url: str, page) -> None:
    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    result = ROUTINES["deterministic:security_headers"](
        tools, f"{demo_target_url}/login", _resolve_secret
    )
    assert result.status == TestStatus.PASSED
