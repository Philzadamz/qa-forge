"""APK upload & analysis (PRD §7.6.3, §10 `POST /apks`)."""

import tempfile
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.config import get_settings
from app.core.rbac import require_project_access, require_user
from app.db.session import get_db
from app.models.apk import Apk
from app.models.project import Project
from app.models.user import User
from app.schemas.apks import ApkOut
from app.services.execution.apk_analysis import ApkAnalysisError, analyze_apk
from app.services.storage import build_storage

router = APIRouter(tags=["apks"])

MAX_APK_BYTES = 200 * 1024 * 1024


def _get_project_or_404(db: Session, project_id: uuid.UUID, user: User) -> Project:
    obj = db.get(Project, project_id)
    if obj is None or obj.deleted_at is not None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Project not found")
    require_project_access(obj, user)
    return obj


@router.get("/projects/{project_id}/apks", response_model=list[ApkOut])
def list_apks(
    project_id: uuid.UUID, db: Session = Depends(get_db), user: User = Depends(require_user)
) -> list[Apk]:
    _get_project_or_404(db, project_id, user)
    return list(
        db.query(Apk).filter(Apk.project_id == project_id).order_by(Apk.created_at.desc()).all()
    )


@router.post(
    "/projects/{project_id}/apks", response_model=ApkOut, status_code=status.HTTP_201_CREATED
)
async def upload_apk(
    project_id: uuid.UUID,
    request: Request,
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> Apk:
    _get_project_or_404(db, project_id, user)
    if not (file.filename or "").lower().endswith(".apk"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Only .apk files are accepted")
    raw = await file.read()
    if len(raw) > MAX_APK_BYTES:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "APK is too large (max 200 MB)")

    settings = get_settings()
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir) / "upload.apk"
        tmp_path.write_bytes(raw)
        try:
            info = analyze_apk(str(tmp_path), aapt_path=settings.android_aapt_path)
        except ApkAnalysisError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    apk_id = uuid.uuid4()
    key = f"apks/{project_id}/{apk_id}.apk"
    build_storage(settings).put(key, raw)

    apk = Apk(
        id=apk_id,
        project_id=project_id,
        uploaded_by=user.id,
        file_key=key,
        file_name=file.filename or "app.apk",
        file_size=len(raw),
        package_name=info.package_name,
        launch_activity=info.launch_activity,
        version_name=info.version_name,
        version_code=info.version_code,
        label=info.label,
    )
    db.add(apk)
    audit_record(
        db,
        actor_id=user.id,
        action="upload",
        entity="apk",
        entity_id=str(apk.id),
        diff={"package_name": info.package_name, "file_name": apk.file_name},
        request=request,
    )
    db.commit()
    db.refresh(apk)
    return apk


@router.delete("/apks/{apk_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_apk(
    apk_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_user),
) -> None:
    apk = db.get(Apk, apk_id)
    if apk is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "APK not found")
    project = db.get(Project, apk.project_id)
    if project is not None:
        require_project_access(project, user)
    build_storage(get_settings()).delete(apk.file_key)
    audit_record(
        db, actor_id=user.id, action="delete", entity="apk", entity_id=str(apk.id), request=request
    )
    db.delete(apk)
    db.commit()
