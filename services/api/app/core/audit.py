"""Audit log helper (ADM-AU-1). Call after every create/update/delete/login/download."""

import json
import uuid

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


def _json_safe(diff: dict[str, object]) -> dict[str, object]:
    """Diffs are built from `payload.model_dump(exclude_unset=True)`, which can carry raw
    UUID/datetime/enum values the stdlib JSON encoder can't serialize — round-trip through
    `default=str` once here so every call site doesn't have to remember to."""
    return json.loads(json.dumps(diff, default=str))  # type: ignore[no-any-return]


def record(
    db: Session,
    *,
    actor_id: uuid.UUID | None,
    action: str,
    entity: str,
    entity_id: str | None = None,
    diff: dict[str, object] | None = None,
    request: Request | None = None,
) -> None:
    ip = request.client.host if request and request.client else None
    db.add(
        AuditLog(
            actor_id=actor_id,
            action=action,
            entity=entity,
            entity_id=entity_id,
            diff=_json_safe(diff) if diff else {},
            ip=ip,
        )
    )
