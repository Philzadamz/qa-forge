"""Fixtures shared by Test Lab (Phase 5/6/7) tests: live `infra/demo-target` (Web) and
`infra/demo-api` (API) servers, a headless Chromium instance, and (if reachable) a real
Android emulator for the Android runner — all session-scoped since they're expensive to start
and safe to share (each test gets its own browser context/page or hits its own resource
paths, so there's no cross-test state collision)."""

import importlib.util
import socket
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
DEMO_TARGET_DIR = REPO_ROOT / "infra" / "demo-target"
DEMO_API_DIR = REPO_ROOT / "infra" / "demo-api"
DEMO_ANDROID_APK = REPO_ROOT / "infra" / "demo-android" / "ApiDemos-debug.apk"


def _load_app_module(path: Path, name: str) -> ModuleType:
    # Loaded by explicit file path, under a name distinct from this repo's own `app` package
    # (services/api/app) — a plain `import app` would hit the already-cached sys.modules
    # entry for that package instead of the fixture app.
    spec = importlib.util.spec_from_file_location(name, path / "app.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


try:
    from playwright.sync_api import Browser, Page, sync_playwright

    _PLAYWRIGHT_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - exercised only when playwright isn't installed
    _PLAYWRIGHT_IMPORT_ERROR = exc


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _start_fastapi_app(module: ModuleType, *, name: str):
    import uvicorn

    port = _free_port()
    config = uvicorn.Config(module.app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        raise RuntimeError(f"{name} did not start in time")

    return f"http://127.0.0.1:{port}", server, thread


@pytest.fixture(scope="session")
def demo_target_url() -> Iterator[str]:
    module = _load_app_module(DEMO_TARGET_DIR, "demo_target_app")
    url, server, thread = _start_fastapi_app(module, name="infra/demo-target")
    yield url
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def demo_api_url() -> Iterator[str]:
    module = _load_app_module(DEMO_API_DIR, "demo_api_app")
    url, server, thread = _start_fastapi_app(module, name="infra/demo-api")
    yield url
    server.should_exit = True
    thread.join(timeout=5)


@pytest.fixture(scope="session")
def _browser() -> Iterator["Browser"]:
    if _PLAYWRIGHT_IMPORT_ERROR is not None:
        pytest.skip(f"playwright not available: {_PLAYWRIGHT_IMPORT_ERROR}")
    with sync_playwright() as pw:
        try:
            browser = pw.chromium.launch(headless=True)
        except Exception as exc:  # pragma: no cover - exercised only without browser binaries
            pytest.skip(f"Chromium not installed for Playwright: {exc}")
        yield browser
        browser.close()


@pytest.fixture
def page(_browser: "Browser") -> Iterator["Page"]:
    context = _browser.new_context()
    pg = context.new_page()
    yield pg
    context.close()


@pytest.fixture(scope="session")
def android_apk_path() -> str:
    if not DEMO_ANDROID_APK.exists():
        pytest.skip("infra/demo-android/ApiDemos-debug.apk not present")
    return str(DEMO_ANDROID_APK)


@pytest.fixture(scope="session")
def android_device_udid() -> str:
    """Skips (doesn't fail) when there's no real Android tooling available — this is live
    device automation, not something every dev machine or CI runner has. Deliberately a short
    boot_timeout: if no warm instance of the configured AVD is already attached, we skip
    rather than spend minutes booting one just for a test run to find out it can't."""
    import httpx

    from app.core.config import get_settings
    from app.services.execution.android_provider import DeviceProviderError, LocalEmulatorProvider

    settings = get_settings()
    try:
        httpx.get(f"{settings.android_appium_url}/status", timeout=3.0)
    except httpx.HTTPError:
        pytest.skip(f"Appium server not reachable at {settings.android_appium_url}")

    provider = LocalEmulatorProvider(
        avd_name=settings.android_avd_name,
        appium_server_url=settings.android_appium_url,
        adb_path=settings.android_adb_path,
        emulator_path=settings.android_emulator_path,
        boot_timeout_seconds=5,
    )
    try:
        device = provider.acquire_device()
    except DeviceProviderError:
        pytest.skip(f"No warm {settings.android_avd_name!r} emulator instance available")
    return device.udid
