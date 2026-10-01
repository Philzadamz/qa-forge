"""Playwright-backed tool implementations for the execution agent (PRD §7.6.1).

Elements are normally addressed by a `ref` the model got from `snapshot()`, assigned via a
`data-qa-ref` attribute injected into the live DOM rather than a real accessibility-tree id —
simpler to implement reliably across arbitrary pages. `snapshot()` only ever surfaces visible,
interactive elements plus a trimmed text dump, approximating the PRD's "accessibility tree +
visible text, trimmed". Deterministic routines (`deterministic.py`), which never call
`snapshot()`, address elements with a real, hand-written CSS selector instead (e.g.
`#username`) — `_locator` tells the two apart by shape (`eN` is always a snapshot ref; the
built-in routines are written against `infra/demo-target`'s known markup specifically because
real CSS selectors need a known target, which only demo-target currently provides).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.sync_api import Locator, Page

_SNAPSHOT_JS = """
() => {
  const interactiveSelector = 'a,button,input,select,textarea,[role="button"],[onclick]';
  const nodes = Array.from(document.querySelectorAll(interactiveSelector));
  let counter = Number(document.documentElement.dataset.qaRefCounter || '0');
  const items = [];
  for (const el of nodes) {
    const style = window.getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;
    let ref = el.getAttribute('data-qa-ref');
    if (!ref) {
      counter += 1;
      ref = 'e' + counter;
      el.setAttribute('data-qa-ref', ref);
    }
    const tag = el.tagName.toLowerCase();
    const label = (el.getAttribute('aria-label') || el.getAttribute('placeholder') ||
                   el.innerText || el.value || el.name || '').trim().slice(0, 80);
    items.push({ref, tag, type: el.getAttribute('type') || '', label});
  }
  document.documentElement.dataset.qaRefCounter = String(counter);
  return {items, bodyText: document.body.innerText.slice(0, 2000)};
}
"""

_SNAPSHOT_REF_RE = re.compile(r"^e\d+$")


class ToolError(Exception):
    pass


class BrowserTools:
    """Thin wrapper around one Playwright `Page`; one instance per case run (PRD §8.4's
    "fresh browser context per case")."""

    def __init__(self, page: Page, *, allowed_url_prefix: str) -> None:
        self.page = page
        self._allowed_url_prefix = allowed_url_prefix

    def _check_allowlist(self, url: str) -> None:
        if not url.startswith(self._allowed_url_prefix):
            raise ToolError(
                f"URL {url!r} is outside the allowlisted target {self._allowed_url_prefix!r}"
            )

    def navigate(self, url: str) -> str:
        self._check_allowlist(url)
        self.page.goto(url, wait_until="domcontentloaded")
        return f"Navigated to {self.page.url}"

    def snapshot(self) -> dict[str, object]:
        result: dict[str, object] = self.page.evaluate(_SNAPSHOT_JS)
        return result

    def screenshot(self) -> bytes:
        shot: bytes = self.page.screenshot(full_page=False)
        return shot

    def _locator(self, ref: str) -> Locator:
        if _SNAPSHOT_REF_RE.match(ref):
            return self.page.locator(f'[data-qa-ref="{ref}"]')
        return self.page.locator(ref)

    def click(self, ref: str) -> str:
        self._locator(ref).click(timeout=5000)
        return f"Clicked {ref}"

    def fill(self, ref: str, value: str) -> str:
        self._locator(ref).fill(value, timeout=5000)
        return f"Filled {ref}"

    def select(self, ref: str, option: str) -> str:
        self._locator(ref).select_option(option, timeout=5000)
        return f"Selected {option!r} in {ref}"

    def press(self, key: str) -> str:
        self.page.keyboard.press(key)
        return f"Pressed {key}"

    def wait_for(
        self, *, text: str | None = None, ref: str | None = None, timeout_ms: int = 5000
    ) -> str:
        from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

        try:
            if ref:
                self._locator(ref).first.wait_for(timeout=timeout_ms)
            elif text:
                self.page.get_by_text(text).first.wait_for(timeout=timeout_ms)
            else:
                raise ToolError("wait_for needs text or ref")
        except PlaywrightTimeoutError as exc:
            raise ToolError(f"Timed out waiting for {ref or text!r}") from exc
        return "ok"

    def assert_visible(self, *, text: str | None = None, ref: str | None = None) -> bool:
        if ref:
            locator = self._locator(ref)
            return bool(locator.count()) and locator.first.is_visible()
        if text:
            locator = self.page.get_by_text(text).first
            return bool(locator.count()) and locator.is_visible()
        raise ToolError("assert_visible needs text or ref")

    def assert_url(self, pattern: str) -> bool:
        return bool(re.search(pattern, self.page.url))

    def back(self) -> str:
        self.page.go_back(wait_until="domcontentloaded")
        return f"Back to {self.page.url}"

    def go_idle(self, minutes: float, *, max_real_seconds: float = 30.0) -> str:
        """Simulated session-timeout wait (PRD §7.6.1): a real wait capped well below what
        `minutes` would literally mean, since the agent can't fast-forward the target's clock.
        Default routines that need a real timeout window configure the target with a short
        session-timeout instead of relying on this for precision."""
        import time

        time.sleep(min(minutes * 60, max_real_seconds))
        return f"Waited ~{min(minutes * 60, max_real_seconds):.0f}s (simulated {minutes}min idle)"
