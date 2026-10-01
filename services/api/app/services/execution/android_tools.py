"""Appium-backed tool implementations for the Android execution agent (PRD §7.6.3, §8.4).

Elements are addressed by a `ref` from `snapshot()`, assigned to interactive nodes (clickable,
scrollable, or text-editable) in the UiAutomator XML page source — the same "assign a short id
to what the model can act on" approach as the Web runner's `data-qa-ref`, except here the ref
maps to a tap point (the center of the node's `bounds`) rather than a selector, since
UiAutomator XML has no stable attribute equivalent to a CSS selector across arbitrary apps.
"""

from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING
from xml.etree import ElementTree

if TYPE_CHECKING:
    from appium.webdriver.webdriver import WebDriver

_BOUNDS_RE = re.compile(r"\[(-?\d+),(-?\d+)\]\[(-?\d+),(-?\d+)\]")
_INTERACTIVE_CLASSES = ("EditText",)
_MAX_SNAPSHOT_NODES = 80


class ToolError(Exception):
    pass


def _parse_bounds(bounds: str) -> tuple[int, int, int, int] | None:
    m = _BOUNDS_RE.match(bounds)
    if not m:
        return None
    x1, y1, x2, y2 = (int(g) for g in m.groups())
    return x1, y1, x2, y2


class AndroidTools:
    def __init__(self, driver: WebDriver, *, package_name: str) -> None:
        self.driver = driver
        self.package_name = package_name
        self._ref_points: dict[str, tuple[int, int]] = {}

    def snapshot(self) -> dict[str, object]:
        source = self.driver.page_source
        # Not untrusted/internet-sourced XML — this is UiAutomator's own dump of the device
        # screen we're already driving via this same Appium session.
        root = ElementTree.fromstring(source)  # noqa: S314
        self._ref_points = {}
        items: list[dict[str, object]] = []
        counter = 0
        for node in root.iter():
            attrib = node.attrib
            clickable = attrib.get("clickable") == "true"
            scrollable = attrib.get("scrollable") == "true"
            editable = any(c in attrib.get("class", "") for c in _INTERACTIVE_CLASSES)
            if not (clickable or scrollable or editable):
                continue
            bounds = _parse_bounds(attrib.get("bounds", ""))
            if bounds is None:
                continue
            x1, y1, x2, y2 = bounds
            if x2 <= x1 or y2 <= y1:
                continue
            counter += 1
            ref = f"e{counter}"
            self._ref_points[ref] = ((x1 + x2) // 2, (y1 + y2) // 2)
            label = (attrib.get("text") or attrib.get("content-desc") or "").strip()[:80]
            items.append(
                {
                    "ref": ref,
                    "class": attrib.get("class", "").rsplit(".", 1)[-1],
                    "label": label,
                    "editable": editable,
                    "scrollable": scrollable,
                }
            )
            if counter >= _MAX_SNAPSHOT_NODES:
                break
        body_text = " ".join(
            (n.attrib.get("text") or "").strip()
            for n in root.iter()
            if (n.attrib.get("text") or "").strip()
        )[:2000]
        return {"items": items, "bodyText": body_text}

    def screenshot(self) -> bytes:
        png: bytes = self.driver.get_screenshot_as_png()
        return png

    def _point(self, ref: str) -> tuple[int, int]:
        point = self._ref_points.get(ref)
        if point is None:
            raise ToolError(f"Unknown ref {ref!r} — call snapshot() first")
        return point

    def tap(self, ref: str) -> str:
        x, y = self._point(ref)
        self.driver.execute_script("mobile: clickGesture", {"x": x, "y": y})
        return f"Tapped {ref}"

    def type(self, ref: str, value: str) -> str:
        x, y = self._point(ref)
        self.driver.execute_script("mobile: clickGesture", {"x": x, "y": y})
        self.driver.execute_script("mobile: type", {"text": value})
        return f"Typed into {ref}"

    def swipe(self, direction: str) -> str:
        if direction not in ("up", "down", "left", "right"):
            raise ToolError(f"Unknown swipe direction {direction!r}")
        size = self.driver.get_window_size()
        width, height = size["width"], size["height"]
        cx, cy = width // 2, height // 2
        offset = min(width, height) // 3
        self.driver.execute_script(
            "mobile: swipeGesture",
            {
                "left": max(cx - offset, 0),
                "top": max(cy - offset, 0),
                "width": min(offset * 2, width),
                "height": min(offset * 2, height),
                "direction": direction,
                "percent": 0.75,
            },
        )
        return f"Swiped {direction}"

    def scroll_to(self, text: str, *, max_swipes: int = 6) -> str:
        for _ in range(max_swipes):
            if self.assert_visible(text):
                return f"Found {text!r}"
            self.swipe("up")
            time.sleep(0.3)
        raise ToolError(f"Could not find {text!r} after scrolling")

    def back(self) -> str:
        self.driver.back()
        return "Pressed back"

    def home(self) -> str:
        self.driver.execute_script("mobile: pressKey", {"keycode": 3})
        return "Pressed home"

    def launch_app(self) -> str:
        self.driver.activate_app(self.package_name)
        return f"Launched {self.package_name}"

    def background_app(self, seconds: float) -> str:
        self.driver.background_app(int(seconds))
        return f"Backgrounded for {seconds}s"

    def rotate(self, orientation: str) -> str:
        normalized = orientation.upper()
        if normalized not in ("PORTRAIT", "LANDSCAPE"):
            raise ToolError(f"Unknown orientation {orientation!r}")
        self.driver.orientation = normalized
        return f"Rotated to {normalized}"

    def wait_for(self, text: str, *, timeout_ms: int = 5000) -> str:
        deadline = time.monotonic() + timeout_ms / 1000
        while time.monotonic() < deadline:
            if self.assert_visible(text):
                return "ok"
            time.sleep(0.3)
        raise ToolError(f"Timed out waiting for {text!r}")

    def assert_visible(self, text: str) -> bool:
        source = self.driver.page_source
        return text in source
