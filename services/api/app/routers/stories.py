"""User stories: upload a file or paste text (PRD §7.3)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.enums import StorySource
from app.core.rbac import require_project_access, require_user
from app.db.session import get_db
from app.models.project import Project
from app.models.user import User
from app.models.user_story import UserStory
from app.schemas.stories import StoryDetailOut, StoryOut, StoryPasteIn
from app.services.ingestion.extract import UnsupportedFileTypeError, extract_text

router = APIRouter(tags=["stories"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _get_project_or_404(db: Session, project_id: uuid.UUID, user: User) -> Project:
    obj = db.get(Project, project_id)
    if obj is None or obj.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_access(obj, user)
    return obj


def _get_story_or_404(db: Session, story_id: uuid.UUID, user: User) -> UserStory:
    obj = db.get(UserStory, story_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Story not found")
    project = db.get(Project, obj.project_id)
    if project is not None:
        require_project_access(project, user)
    return obj


@router.get("/projects/{project_id}/stories", response_model=list[StoryOut])
def list_stories(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[UserStory]:
    _get_project_or_404(db, project_id, user)
    return list(
        db.query(UserStory)
        .filter(UserStory.project_id == project_id)
        .order_by(UserStory.created_at.desc())
        .all()
    )


@router.post(
    "/projects/{project_id}/stories/upload",
    response_model=StoryOut,
    status_code=status.HTTP_201_CREATED,
)
async def upload_story(
    project_id: uuid.UUID,
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> UserStory:
    _get_project_or_404(db, project_id, user)
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "File is too large (max 20 MB)")
    try:
        text = extract_text(file.filename or "story.txt", raw)
    except UnsupportedFileTypeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    if not text.strip():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "No text could be extracted from this file"
        )

    obj = UserStory(
        project_id=project_id,
        title=file.filename or "Uploaded story",
        source=StorySource.UPLOAD,
        raw_text=text,
        extracted_text=text,
        uploaded_by=user.id,
    )
    db.add(obj)
    db.flush()
    audit_record(
        db,
        actor_id=user.id,
        action="upload",
        entity="user_story",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.post(
    "/projects/{project_id}/stories/paste",
    response_model=StoryOut,
    status_code=status.HTTP_201_CREATED,
)
def paste_story(
    project_id: uuid.UUID,
    payload: StoryPasteIn,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> UserStory:
    _get_project_or_404(db, project_id, user)
    obj = UserStory(
        project_id=project_id,
        title=payload.title,
        source=StorySource.PASTE,
        raw_text=payload.text,
        extracted_text=payload.text,
        uploaded_by=user.id,
    )
    db.add(obj)
    db.flush()
    audit_record(
        db,
        actor_id=user.id,
        action="paste",
        entity="user_story",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/stories/{story_id}", response_model=StoryDetailOut)
def get_story(
    story_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> UserStory:
    return _get_story_or_404(db, story_id, user)
