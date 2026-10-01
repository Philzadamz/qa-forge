"""Exercises the real `AndroidTools` wrapper against a real Appium session driving a real
emulator and `infra/demo-android`'s sample app — the thing the unit tests (fake doubles)
can't prove. Skips gracefully (see `android_device_udid`) when no emulator/Appium is
reachable, rather than failing.

The APK is installed once per test module, not per test: reinstalling it before every test
function (combined with a fresh Appium session each time) proved flaky in practice — a
session could start on the home launcher instead of the app, or time out talking to the
device. The real runner (`android_execution_runner.py`) also installs once per *run*, not per
case, and force-stops + relaunches between cases — this fixture mirrors that instead of a
full reinstall each time.
"""

import subprocess

import pytest

from app.core.config import get_settings
from app.services.execution.android_tools import AndroidTools, ToolError

PACKAGE = "io.appium.android.apis"
ACTIVITY = ".ApiDemos"


@pytest.fixture(scope="module")
def installed_app(android_apk_path: str, android_device_udid: str) -> str:
    settings = get_settings()
    subprocess.run(
        [settings.android_adb_path, "-s", android_device_udid, "install", "-r", android_apk_path],
        check=True,
        capture_output=True,
        timeout=60,
    )
    yield android_device_udid
    subprocess.run(
        [settings.android_adb_path, "-s", android_device_udid, "uninstall", PACKAGE],
        capture_output=True,
        timeout=30,
    )


@pytest.fixture
def driver(installed_app: str):
    from appium import webdriver
    from appium.options.android import UiAutomator2Options

    settings = get_settings()
    # Force-stop + let Appium relaunch fresh for each test — the same isolation the real
    # runner uses between cases, without the flakiness a full reinstall caused here.
    subprocess.run(
        [settings.android_adb_path, "-s", installed_app, "shell", "am", "force-stop", PACKAGE],
        capture_output=True,
        timeout=15,
    )
    options = UiAutomator2Options()
    options.platform_name = "Android"
    options.udid = installed_app
    options.automation_name = "UiAutomator2"
    options.app_package = PACKAGE
    options.app_activity = ACTIVITY
    options.no_reset = True
    d = webdriver.Remote(settings.android_appium_url, options=options)
    yield d
    d.quit()


def test_snapshot_finds_the_category_list(driver) -> None:
    tools = AndroidTools(driver, package_name=PACKAGE)
    snap = tools.snapshot()
    labels = {item["label"] for item in snap["items"]}
    assert "Views" in labels
    assert "Animation" in labels


def test_tap_navigates_and_back_returns(driver) -> None:
    tools = AndroidTools(driver, package_name=PACKAGE)
    snap = tools.snapshot()
    views_ref = next(i["ref"] for i in snap["items"] if i["label"] == "Views")
    tools.tap(views_ref)
    assert tools.assert_visible("Animation")
    tools.back()
    assert tools.assert_visible("Views")


def test_screenshot_returns_png_bytes(driver) -> None:
    tools = AndroidTools(driver, package_name=PACKAGE)
    shot = tools.screenshot()
    assert shot[:8] == b"\x89PNG\r\n\x1a\n"


def test_scroll_to_unknown_text_raises_tool_error(driver) -> None:
    tools = AndroidTools(driver, package_name=PACKAGE)
    with pytest.raises(ToolError):
        tools.scroll_to("Definitely Not A Real Menu Item XYZ", max_swipes=2)


def test_tap_unknown_ref_raises_tool_error(driver) -> None:
    tools = AndroidTools(driver, package_name=PACKAGE)
    with pytest.raises(ToolError):
        tools.tap("e999")
