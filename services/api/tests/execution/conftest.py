"""Fixtures shared by Test Lab (Phase 5/6) tests: live `infra/demo-target` (Web) and
`infra/demo-api` (API) servers, and a headless Chromium instance — all session-scoped since
they're expensive to start and safe to share (each test gets its own browser context/page or
hits its own resource paths, so there's no cross-test state collision)."""

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
