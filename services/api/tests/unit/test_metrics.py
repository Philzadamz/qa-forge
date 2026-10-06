from datetime import UTC, datetime, timedelta

from app.core.metrics import run_duration_seconds


def test_duration_handles_naive_start_with_aware_finish() -> None:
    finished = datetime(2026, 10, 4, 12, 0, 30, tzinfo=UTC)
    started_naive = datetime(2026, 10, 4, 12, 0, 0)
    assert run_duration_seconds(started_naive, finished) == 30.0


def test_duration_between_two_aware_datetimes() -> None:
    finished = datetime(2026, 10, 4, 12, 5, tzinfo=UTC)
    assert run_duration_seconds(finished - timedelta(minutes=2), finished) == 120.0


def test_duration_is_zero_when_a_timestamp_is_missing() -> None:
    assert run_duration_seconds(None, datetime.now(UTC)) == 0.0
