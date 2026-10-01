"""Admin: report defaults (ADM-RD-1..4) — exit criteria, approval roles, classification
label, and reusable comment snippets."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.rbac import require_admin
from app.db.session import get_db
from app.models.note_snippet import NoteSnippet
from app.models.report_defaults import ReportDefaults
from app.models.user import User
from app.schemas.admin import (
    NoteSnippetIn,
    NoteSnippetOut,
    NoteSnippetPatch,
    ReportDefaultsIn,
    ReportDefaultsOut,
)

router = APIRouter(tags=["admin:report-defaults"])


def _get_or_create_singleton(db: Session) -> ReportDefaults:
    obj = db.query(ReportDefaults).order_by(ReportDefaults.created_at).first()
    if obj is None:
        obj = ReportDefaults()
        db.add(obj)
        db.flush()
    return obj


@router.get("/report-defaults", response_model=ReportDefaultsOut)
def get_report_defaults(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> ReportDefaults:
    return _get_or_create_singleton(db)


@router.put("/report-defaults", response_model=ReportDefaultsOut)
def update_report_defaults(
    payload: ReportDefaultsIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> ReportDefaults:
    obj = _get_or_create_singleton(db)
    obj.exit_criteria = payload.exit_criteria
    obj.approval_roles = [r.model_dump() for r in payload.approval_roles]
    obj.classification_label = payload.classification_label
    obj.organisation_name = payload.organisation_name
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="report_defaults",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


def _get_snippet_or_404(db: Session, snippet_id: uuid.UUID) -> NoteSnippet:
    obj = db.get(NoteSnippet, snippet_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Snippet not found")
    return obj


@router.get("/snippets", response_model=list[NoteSnippetOut])
def list_snippets(
    db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> list[NoteSnippet]:
    return list(db.query(NoteSnippet).order_by(NoteSnippet.title).all())


@router.post("/snippets", response_model=NoteSnippetOut, status_code=status.HTTP_201_CREATED)
def create_snippet(
    payload: NoteSnippetIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> NoteSnippet:
    obj = NoteSnippet(**payload.model_dump())
    db.add(obj)
    db.flush()
    audit_record(
        db,
        actor_id=user.id,
        action="create",
        entity="note_snippet",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.patch("/snippets/{snippet_id}", response_model=NoteSnippetOut)
def update_snippet(
    snippet_id: uuid.UUID,
    payload: NoteSnippetPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> NoteSnippet:
    obj = _get_snippet_or_404(db, snippet_id)
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="note_snippet",
        entity_id=str(obj.id),
        diff=changes,
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/snippets/{snippet_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_snippet(
    snippet_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> None:
    obj = _get_snippet_or_404(db, snippet_id)
    audit_record(
        db,
        actor_id=user.id,
        action="delete",
        entity="note_snippet",
        entity_id=str(snippet_id),
        request=request,
    )
    db.delete(obj)
    db.commit()
