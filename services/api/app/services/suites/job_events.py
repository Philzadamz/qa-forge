"""In-process pub/sub for generation-job progress (PRD: SSE stream of cases).

Single-process only, like `core/rate_limit.py` — fine for local/single-server deployments
(docs/decisions/001); a multi-worker deployment needs a shared bus (Redis pub/sub) instead.
"""

import queue
import threading
from typing import TypedDict


class JobEvent(TypedDict, total=False):
    type: str  # "feature_done" | "job_done"
    feature: str
    case_count: int
    status: str
    error: str


_lock = threading.Lock()
_subscribers: dict[str, list["queue.Queue[JobEvent]"]] = {}


def subscribe(job_id: str) -> "queue.Queue[JobEvent]":
    q: queue.Queue[JobEvent] = queue.Queue()
    with _lock:
        _subscribers.setdefault(job_id, []).append(q)
    return q


def unsubscribe(job_id: str, q: "queue.Queue[JobEvent]") -> None:
    with _lock:
        subs = _subscribers.get(job_id, [])
        if q in subs:
            subs.remove(q)
        if not subs and job_id in _subscribers:
            del _subscribers[job_id]


def publish(job_id: str, event: JobEvent) -> None:
    with _lock:
        subs = list(_subscribers.get(job_id, []))
    for q in subs:
        q.put(event)
