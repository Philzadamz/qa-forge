"""In-process pub/sub for Test Lab run progress (PRD §7.6 live run view), mirroring
`suites/job_events.py` — single-process only (docs/decisions/001); a multi-worker deployment
needs a shared bus (Redis pub/sub) instead.
"""

import queue
import threading
from typing import TypedDict


class RunEvent(TypedDict, total=False):
    type: str  # "case_started" | "step" | "case_done" | "run_done"
    case_id: str
    display_id: str
    seq: int
    action: str
    outcome: str
    message: str
    has_screenshot: bool
    status: str
    error: str


_lock = threading.Lock()
_subscribers: dict[str, list["queue.Queue[RunEvent]"]] = {}
# Cooperative cancellation (PRD §7.6 "Stop button"): checked between cases, not mid-action —
# an in-flight Playwright call still completes, but no further case starts.
_cancelled: set[str] = set()


def request_cancel(run_id: str) -> None:
    with _lock:
        _cancelled.add(run_id)


def is_cancelled(run_id: str) -> bool:
    with _lock:
        return run_id in _cancelled


def clear_cancel(run_id: str) -> None:
    with _lock:
        _cancelled.discard(run_id)


def subscribe(run_id: str) -> "queue.Queue[RunEvent]":
    q: queue.Queue[RunEvent] = queue.Queue()
    with _lock:
        _subscribers.setdefault(run_id, []).append(q)
    return q


def unsubscribe(run_id: str, q: "queue.Queue[RunEvent]") -> None:
    with _lock:
        subs = _subscribers.get(run_id, [])
        if q in subs:
            subs.remove(q)
        if not subs and run_id in _subscribers:
            del _subscribers[run_id]


def publish(run_id: str, event: RunEvent) -> None:
    with _lock:
        subs = list(_subscribers.get(run_id, []))
    for q in subs:
        q.put(event)
