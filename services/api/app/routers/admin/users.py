"""Admin: user management (ADM-UP-1)."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.rbac import require_admin
from app.core.security import hash_password
from app.db.session import get_db
from app.models.user import User
from app.schemas.admin import UserCreate, UserOut, UserPasswordSet, UserPatch

router = APIRouter(prefix="/users", tags=["admin:users"])


def _get_user_or_404(db: Session, user_id: uuid.UUID) -> User:
    obj = db.get(User, user_id)
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return obj


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), _: User = Depends(require_admin)) -> list[User]:
    return list(db.query(User).order_by(User.full_name).all())


@router.post("", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> User:
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).one_or_none():
        raise HTTPException(status.HTTP_409_CONFLICT, "A user with this email already exists")
    obj = User(
        email=email,
        full_name=payload.full_name,
        staff_id=payload.staff_id,
        role=payload.role,
        password_hash=hash_password(payload.password),
    )
    db.add(obj)
    db.flush()
    audit_record(
        db, actor_id=user.id, action="create", entity="user", entity_id=str(obj.id), request=request
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: uuid.UUID, db: Session = Depends(get_db), _: User = Depends(require_admin)
) -> User:
    return _get_user_or_404(db, user_id)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: uuid.UUID,
    payload: UserPatch,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> User:
    obj = _get_user_or_404(db, user_id)
    if obj.id == user.id and payload.is_active is False:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot deactivate your own account")
    if obj.id == user.id and payload.role is not None and payload.role != obj.role:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot change your own role")
    changes = payload.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(obj, key, value)
    audit_record(
        db,
        actor_id=user.id,
        action="update",
        entity="user",
        entity_id=str(obj.id),
        diff=changes,
        request=request,
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.post("/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_user_password(
    user_id: uuid.UUID,
    payload: UserPasswordSet,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_admin),
) -> None:
    obj = _get_user_or_404(db, user_id)
    obj.password_hash = hash_password(payload.new_password)
    audit_record(
        db,
        actor_id=user.id,
        action="reset_password",
        entity="user",
        entity_id=str(obj.id),
        request=request,
    )
    db.commit()
