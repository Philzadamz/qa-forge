"""Measure the PRD §12 performance targets that can run without a live LLM or device.

Runs against a throwaway SQLite database and storage root, never the dev DB:

    uv run python scripts/measure_targets.py

Prints a markdown table of median latencies. Story generation (< 3 min) and Test Lab runs
need a real provider key / emulator and are measured separately (see docs/performance.md).
"""

import os
import statistics
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

WORKDIR = Path(tempfile.mkdtemp(prefix="qaforge-perf-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(WORKDIR / 'perf.db').as_posix()}"
os.environ["STORAGE_LOCAL_ROOT"] = str(WORKDIR / "storage")
os.environ["JWT_SECRET"] = "perf-secret-key-at-least-32-bytes-long!!"  # noqa: S105 - throwaway DB
os.environ["ENVIRONMENT"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

from app.cli import DEFAULT_TEMPLATE_PATH, seed_defaults, seed_report_defaults  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.session import get_engine, get_sessionmaker  # noqa: E402
from app.main import create_app  # noqa: E402
from app.models import Base  # noqa: E402
from app.models.test_case_type import TestCaseType  # noqa: E402
from app.models.user import User  # noqa: E402

CASE_COUNT = 300
REPEATS = 5


def _median_ms(fn: Callable[[], object], repeats: int = REPEATS) -> float:
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - started) * 1000)
    return statistics.median(samples)


def main() -> None:
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_sessionmaker.cache_clear()
    Base.metadata.create_all(get_engine())

    session = get_sessionmaker()()
    session.add(
        User(
            email="perf@example.com",
            full_name="Perf",
            role="admin",
            password_hash=hash_password("perf-password-1"),
        )
    )
    session.commit()
    session.close()
    seed_defaults(DEFAULT_TEMPLATE_PATH)
    seed_report_defaults()

    session = get_sessionmaker()()
    type_obj = session.query(TestCaseType).filter(TestCaseType.name == "Web Application").one()
    type_id = str(type_obj.id)
    session.close()

    client = TestClient(create_app())
    login = client.post(
        "/api/v1/auth/login", json={"email": "perf@example.com", "password": "perf-password-1"}
    )
    if login.status_code != 200:
        raise RuntimeError(f"login failed: {login.text}")

    project = client.post(
        "/api/v1/projects", json={"name": "Perf", "app_code": "PERF", "id_prefix": "Perf"}
    ).json()
    suite = client.post(
        "/api/v1/suites",
        json={
            "project_id": project["id"],
            "type_id": type_id,
            "name": "Perf suite",
            "header": {"project_name_line": "PERF: Perf suite"},
        },
    ).json()
    suite_id = suite["id"]

    for i in range(CASE_COUNT):
        resp = client.post(
            f"/api/v1/suites/{suite_id}/cases",
            json={
                "section": "functional",
                "feature": f"Feature {i % 12}",
                "scenario": f"Scenario {i}",
                "steps": ["Open the page", "Perform the action"],
                "expected_result": "The expected outcome is shown",
            },
        )
        if resp.status_code != 201:
            raise RuntimeError(f"case create failed: {resp.text}")

    defaults_ms = _median_ms(lambda: client.get(f"/api/v1/types/{type_id}/defaults"))
    xlsx_ms = _median_ms(lambda: client.post(f"/api/v1/suites/{suite_id}/export/xlsx"), repeats=3)

    report = client.post(f"/api/v1/suites/{suite_id}/reports/draft").json()
    report_id = report["id"]
    docx_ms = _median_ms(
        lambda: client.post(f"/api/v1/reports/{report_id}/render?format=docx"), repeats=3
    )

    print("| Target (PRD §12) | Requirement | Measured (median) | Result |")
    print("|---|---|---|---|")
    print(
        f"| Defaults render | < 500 ms | {defaults_ms:.0f} ms (31 defaults) | "
        f"{'pass' if defaults_ms < 500 else 'FAIL'} |"
    )
    print(
        f"| xlsx export | < 10 s for 300 cases | {xlsx_ms:.0f} ms ({CASE_COUNT} cases) | "
        f"{'pass' if xlsx_ms < 10_000 else 'FAIL'} |"
    )
    print(f"| docx render | < 5 s | {docx_ms:.0f} ms | {'pass' if docx_ms < 5_000 else 'FAIL'} |")


if __name__ == "__main__":
    main()
