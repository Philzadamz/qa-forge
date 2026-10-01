"""Test double for `AndroidTools` (mirrors `fake_browser_tools.py`'s role for the Web runner):
records every call and lets a test script canned responses, so agent-loop logic tests don't
need a real emulator. Real `AndroidTools` behavior against a real device is covered separately
by `tests/execution/` (a real emulator + Appium + `infra/demo-android`)."""

from dataclasses import dataclass, field


@dataclass
class FakeAndroidTools:
    wait_for_fails: set[str] = field(default_factory=set)
    assert_visible_results: dict[str, bool] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, object]]] = field(default_factory=list)
    screenshot_bytes: bytes = b"\x89PNG-fake"

    def snapshot(self) -> dict[str, object]:
        self.calls.append(("snapshot", {}))
        return {"items": [], "bodyText": ""}

    def screenshot(self) -> bytes:
        self.calls.append(("screenshot", {}))
        return self.screenshot_bytes

    def tap(self, ref: str) -> str:
        self.calls.append(("tap", {"ref": ref}))
        return f"Tapped {ref}"

    def type(self, ref: str, value: str) -> str:
        self.calls.append(("type", {"ref": ref, "value": value}))
        return f"Typed into {ref}"

    def swipe(self, direction: str) -> str:
        self.calls.append(("swipe", {"direction": direction}))
        return f"Swiped {direction}"

    def scroll_to(self, text: str) -> str:
        self.calls.append(("scroll_to", {"text": text}))
        if text in self.wait_for_fails:
            from app.services.execution.android_tools import ToolError

            raise ToolError(f"Could not find {text!r} after scrolling")
        return f"Found {text!r}"

    def back(self) -> str:
        self.calls.append(("back", {}))
        return "Pressed back"

    def home(self) -> str:
        self.calls.append(("home", {}))
        return "Pressed home"

    def launch_app(self) -> str:
        self.calls.append(("launch_app", {}))
        return "Launched"

    def background_app(self, seconds: float) -> str:
        self.calls.append(("background_app", {"seconds": seconds}))
        return f"Backgrounded for {seconds}s"

    def rotate(self, orientation: str) -> str:
        self.calls.append(("rotate", {"orientation": orientation}))
        return f"Rotated to {orientation}"

    def wait_for(self, text: str, *, timeout_ms: int = 5000) -> str:
        self.calls.append(("wait_for", {"text": text}))
        if text in self.wait_for_fails:
            from app.services.execution.android_tools import ToolError

            raise ToolError(f"Timed out waiting for {text!r}")
        return "ok"

    def assert_visible(self, text: str) -> bool:
        self.calls.append(("assert_visible", {"text": text}))
        return self.assert_visible_results.get(text, True)
