"""In-process fixed-window rate limiter for login (PRD §12: 5/min).

Single-process only — fine for local/single-server deployments (docs/decisions/001).
A multi-worker/production deployment needs a shared store (Redis) instead.
"""

import time
from collections import defaultdict

_WINDOW_SECONDS = 60
_hits: dict[str, list[float]] = defaultdict(list)


def check(key: str, *, limit: int = 5, window_seconds: int = _WINDOW_SECONDS) -> bool:
    """Record a hit for `key` and return True if it's still within the limit."""
    now = time.monotonic()
    cutoff = now - window_seconds
    recent = [t for t in _hits[key] if t > cutoff]
    recent.append(now)
    _hits[key] = recent
    return len(recent) <= limit


def reset() -> None:
    """Test helper."""
    _hits.clear()
