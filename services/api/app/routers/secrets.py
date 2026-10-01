"""Project-scoped secrets for Test Lab runs (PRD §5, §7.6). Values are write-only: encrypted
at rest, decrypted server-side only when a run resolves a `secret_ref` immediately before
using it, and never included in any response or AI call."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.config import get_settings
from app.core.crypto import encrypt_secret
from app.core.rbac import require_project_access, require_user
from app.db.session import get_db
from app.models.project import Project
from app.models.secret import Secret
from app.models.user import User
from app.schemas.secrets import SecretIn, SecretOut

router = APIRouter(tags=["secrets"])


def _get_project_or_404(db: Session, project_id: uuid.UUID, user: User) -> Project:
    obj = db.get(Project, project_id)
    if obj is None or obj.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_access(obj, user)
    return obj


@router.get("/projects/{project_id}/secrets", response_model=list[SecretOut])
def list_secrets(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[Secret]:
    _get_project_or_404(db, project_id, user)
    return list(
        db.query(Secret)
        .filter(Secret.project_id == project_id)
        .order_by(Secret.created_at.desc())
        .all()
    )


@router.post(
    "/projects/{project_id}/secrets", response_model=SecretOut, status_code=status.HTTP_201_CREATED
)
def create_secret(
    project_id: uuid.UUID,
    payload: SecretIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Secret:
    _get_project_or_404(db, project_id, user)
    existing = (
        db.query(Secret)
        .filter(Secret.project_id == project_id, Secret.name == payload.name)
        .first()
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "A secret with this name already exists")
    settings = get_settings()
    secret = Secret(
        owner_id=user.id,
        project_id=project_id,
        name=payload.name,
        kind=payload.kind,
        ciphertext=encrypt_secret(payload.value, settings),
    )
    db.add(secret)
    audit_record(
        db,
        actor_id=user.id,
        action="create",
        entity="secret",
        entity_id=str(secret.id),
        diff={"name": payload.name, "kind": payload.kind},
        request=request,
    )
    db.commit()
    db.refresh(secret)
    return secret


@router.delete("/secrets/{secret_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_secret(
    secret_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    secret = db.get(Secret, secret_id)
    if secret is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Secret not found")
    project = db.get(Project, secret.project_id)
    if project is not None:
        require_project_access(project, user)
    audit_record(
        db,
        actor_id=user.id,
        action="delete",
        entity="secret",
        entity_id=str(secret.id),
        request=request,
    )
    db.delete(secret)
    db.commit()
