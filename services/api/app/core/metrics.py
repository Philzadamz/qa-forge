"""Prometheus metrics (PRD §12 Observability: jobs, run durations, token usage).

Exposed at `GET /metrics` from the API process. Counters are per process — a multi-worker
deployment needs `PROMETHEUS_MULTIPROC_DIR` (docs/decisions/001 describes the single-process
local setup this targets).
"""

from datetime import UTC, datetime

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

AI_TOKENS = Counter(
    "qaforge_ai_tokens_total",
    "Tokens sent to or received from the model provider.",
    ["model", "direction"],
)
GENERATION_JOBS = Counter(
    "qaforge_generation_jobs_total",
    "Story-to-cases generation jobs finished, by outcome.",
    ["status"],
)
RUN_DURATION = Histogram(
    "qaforge_run_duration_seconds",
    "Wall-clock duration of Test Lab runs, by target and final status.",
    ["target", "status"],
    buckets=(5, 15, 30, 60, 120, 300, 600, 1200, 1800),
)


def run_duration_seconds(started: datetime | None, finished: datetime | None) -> float:
    # SQLite hands back naive datetimes after a commit, while in-memory values are aware UTC —
    # normalize both sides, or the subtraction raises and marks a finished run as errored.
    if started is None or finished is None:
        return 0.0
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    if finished.tzinfo is None:
        finished = finished.replace(tzinfo=UTC)
    return (finished - started).total_seconds()


def render() -> tuple[bytes, str]:
    return generate_latest(), CONTENT_TYPE_LATEST
