"""Test double for `BrowserTools` (mirrors `FakeLLMClient`'s role for the AI client):
records every call and lets a test script canned responses, so execution-logic tests don't
need a real browser. Real `BrowserTools` behavior against a real page is covered separately
by `tests/execution/` (Playwright + `infra/demo-target`)."""

from dataclasses import dataclass, field


@dataclass
class FakeBrowserTools:
    wait_for_fails: set[str] = field(default_factory=set)  # refs/texts that should time out
    assert_visible_results: dict[str, bool] = field(default_factory=dict)
    assert_url_result: bool = True
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)
    screenshot_bytes: bytes = b"\x89PNG-fake"

    def navigate(self, url: str) -> str:
        self.calls.append(("navigate", {"url": url}))
        return f"Navigated to {url}"

    def snapshot(self) -> dict[str, object]:
        self.calls.append(("snapshot", {}))
        return {"items": [], "bodyText": ""}

    def screenshot(self) -> bytes:
        self.calls.append(("screenshot", {}))
        return self.screenshot_bytes

    def click(self, ref: str) -> str:
        self.calls.append(("click", {"ref": ref}))
        return f"Clicked {ref}"

    def fill(self, ref: str, value: str) -> str:
        self.calls.append(("fill", {"ref": ref, "value": value}))
        return f"Filled {ref}"

    def select(self, ref: str, option: str) -> str:
        self.calls.append(("select", {"ref": ref, "option": option}))
        return f"Selected {option} in {ref}"

    def press(self, key: str) -> str:
        self.calls.append(("press", {"key": key}))
        return f"Pressed {key}"

    def wait_for(
        self, *, text: str | None = None, ref: str | None = None, timeout_ms: int = 5000
    ) -> str:
        self.calls.append(("wait_for", {"text": text, "ref": ref}))
        target = ref or text or ""
        if target in self.wait_for_fails:
            from app.services.execution.tools import ToolError

            raise ToolError(f"Timed out waiting for {target!r}")
        return "ok"

    def assert_visible(self, *, text: str | None = None, ref: str | None = None) -> bool:
        self.calls.append(("assert_visible", {"text": text, "ref": ref}))
        return self.assert_visible_results.get(ref or text or "", True)

    def assert_url(self, pattern: str) -> bool:
        self.calls.append(("assert_url", {"pattern": pattern}))
        return self.assert_url_result

    def back(self) -> str:
        self.calls.append(("back", {}))
        return "Back"

    def go_idle(self, minutes: float, *, max_real_seconds: float = 30.0) -> str:
        self.calls.append(("go_idle", {"minutes": minutes}))
        return f"Waited ~{min(minutes * 60, max_real_seconds):.0f}s"
