"""Projects (USR-PR-1/2). Users see only projects they own or are a member of; admins see
all and can reassign ownership (ADM-UP-2)."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.config import get_settings
from app.core.rbac import require_project_access, require_user
from app.db.session import get_db
from app.models.project import Project
from app.models.user import User
from app.schemas.projects import ProjectIn, ProjectOut, ProjectPatch
from app.services.retention import purge_project_storage
from app.services.storage import build_storage

router = APIRouter(prefix="/projects", tags=["projects"])


def _get_project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    obj = db.get(Project, project_id)
    if obj is None or obj.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    return obj


@router.get("", response_model=list[ProjectOut])
def list_projects(
    db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[Project]:
    query = db.query(Project).filter(Project.deleted_at.is_(None))
    if user.role != "admin":
        # SQLite/Postgres JSON `members` is a list of id strings; filter in Python since a
        # portable "value in JSON array" query isn't worth the dialect-specific complexity
        # at this scale (a handful of projects per user, not millions).
        candidates = query.filter(Project.owner_id == user.id).all()
        others = query.filter(Project.owner_id != user.id).all()
        candidates.extend(p for p in others if str(user.id) in p.members)
        return candidates
    return list(query.order_by(Project.name).all())


@router.post("", response_model=ProjectOut, status_code=status.HTTP_201_CREATED)
def create_project(
    payload: ProjectIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Project:
    obj = Project(
        **payload.model_dump(exclude={"members"}),
        owner_id=user.id,
        members=[str(m) for m in payload.members],
    )
    db.add(obj)
    db.flush()
    audit_record(
        db,
        actor_id=user.id,
        action="create",
        entity="project",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{project_id}", response_model=ProjectOut)
def get_project(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> Project:
    obj = _get_project_or_404(db, project_id)
    require_project_access(obj, user)
    return obj


@router.patch("/{project_id}", response_model=ProjectOut)
def update_project(
    project_id: uuid.UUID,
    payload: ProjectPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Project:
    obj = _get_project_or_404(db, project_id)
    require_project_access(obj, user)
    changes = payload.model_dump(exclude_unset=True)
    if "owner_id" in changes and user.role != "admin":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only an admin can reassign a project's owner"
        )
    if "members" in changes:
        changes["members"] = [str(m) for m in changes["members"]]
    for key, value in changes.items():
        setattr(obj, key, value)
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="project",
        entity_id=str(obj.id),
        diff=changes,
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    obj = _get_project_or_404(db, project_id)
    require_project_access(obj, user)
    storage = build_storage(get_settings())
    purge_counts = purge_project_storage(db, storage, project_id)
    obj.deleted_at = datetime.now(UTC)
    audit_record(
        db,
        actor_id=user.id,
        action="delete",
        entity="project",
        entity_id=str(project_id),
        diff={
            "purged_evidence": purge_counts.evidence,
            "purged_stories": purge_counts.stories,
            "purged_reports": purge_counts.reports,
            "purged_apks": purge_counts.apks,
        },
        request=request,
    )
    db.commit()
