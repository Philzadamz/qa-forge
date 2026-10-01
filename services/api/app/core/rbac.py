"""Auth dependency + role checks. Every protected endpoint depends on one of these."""

import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import ACCESS_COOKIE, decode_token
from app.db.session import get_db
from app.models.project import Project
from app.models.user import User


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    settings = get_settings()
    try:
        payload = decode_token(token, settings=settings, expected_type="access")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session") from exc
    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    return user


def require_role(*roles: str) -> Callable[[User], User]:
    def _check(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return _check


require_admin = require_role("admin")
require_user = require_role("admin", "user")


def can_access_project(user: User, project: Project) -> bool:
    return (
        user.role == "admin"
        or str(user.id) == str(project.owner_id)
        or str(user.id) in project.members
    )


def require_project_access(project: Project, user: User) -> None:
    if not can_access_project(user, project):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "You don't have access to this project")
