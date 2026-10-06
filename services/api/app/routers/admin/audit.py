"""Admin: read-only audit log viewer (ADM-AU-1, PRD §12 "audit log complete")."""

import datetime as dt
import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.rbac import require_admin
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.admin import AuditLogOut

router = APIRouter(prefix="/audit-log", tags=["admin:audit"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
    action: str | None = Query(None, max_length=100),
    entity: str | None = Query(None, max_length=100),
    actor_id: uuid.UUID | None = None,
    since: dt.datetime | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[AuditLog]:
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity:
        query = query.filter(AuditLog.entity == entity)
    if actor_id:
        query = query.filter(AuditLog.actor_id == actor_id)
    if since:
        query = query.filter(AuditLog.at >= since)
    return list(query.order_by(AuditLog.at.desc()).offset(offset).limit(limit).all())
