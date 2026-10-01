"""Exercises the real `BrowserTools` wrapper against a real headless Chromium page and the
real `infra/demo-target` app — the thing the unit tests (fake doubles) can't prove."""

from app.services.execution.tools import BrowserTools


def test_snapshot_assigns_stable_refs(demo_target_url: str, page) -> None:
    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    tools.navigate(f"{demo_target_url}/login")
    snap = tools.snapshot()
    refs = {item["ref"] for item in snap["items"]}
    assert any("username" in item["label"] or item["tag"] == "input" for item in snap["items"])
    assert refs  # at least one interactive element found

    snap2 = tools.snapshot()
    assert {i["ref"] for i in snap2["items"]} == refs  # refs are stable across snapshots


def test_fill_and_click_logs_in(demo_target_url: str, page) -> None:
    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    tools.navigate(f"{demo_target_url}/login")
    tools.fill("#username", "demo")
    tools.fill("#password", "Demo12345!")
    tools.click("button[type=submit]")
    tools.wait_for(ref="#welcome", timeout_ms=5000)
    assert tools.assert_visible(ref="#welcome")
    assert tools.assert_url(r"/dashboard$")


def test_navigate_outside_allowlist_is_rejected(demo_target_url: str, page) -> None:
    from app.services.execution.tools import ToolError

    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    try:
        tools.navigate("http://example.invalid/evil")
    except ToolError as exc:
        assert "allowlisted" in str(exc)
    else:
        raise AssertionError("expected a ToolError for a non-allowlisted URL")


def test_assert_visible_false_for_missing_element(demo_target_url: str, page) -> None:
    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    tools.navigate(f"{demo_target_url}/login")
    assert tools.assert_visible(ref="[data-qa-ref='does-not-exist']") is False


def test_screenshot_returns_png_bytes(demo_target_url: str, page) -> None:
    tools = BrowserTools(page, allowed_url_prefix=demo_target_url)
    tools.navigate(f"{demo_target_url}/login")
    shot = tools.screenshot()
    assert shot[:8] == b"\x89PNG\r\n\x1a\n"
