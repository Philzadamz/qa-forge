"""Login, refresh, logout, /me, and password reset (PRD §2, §10)."""

import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.audit import record as audit_record
from app.core.config import get_settings
from app.core.rate_limit import check as rate_limit_check
from app.core.rbac import get_current_user
from app.core.security import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    decode_token,
    hash_password,
    set_auth_cookies,
    verify_password,
)
from app.db.base import utcnow
from app.db.session import get_db
from app.models.password_reset_token import PasswordResetToken
from app.models.user import User
from app.schemas.auth import ForgotPasswordRequest, LoginRequest, MeResponse, ResetPasswordRequest

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

RESET_TOKEN_TTL = timedelta(hours=1)


@router.post("/login", response_model=MeResponse)
def login(
    payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)
) -> User:
    client_host = request.client.host if request.client else "unknown"
    if not rate_limit_check(f"login:{client_host}:{payload.email.lower()}"):
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts")

    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if (
        user is None
        or not user.is_active
        or not verify_password(payload.password, user.password_hash)
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password")

    user.last_login_at = utcnow()
    audit_record(
        db, actor_id=user.id, action="login", entity="user", entity_id=str(user.id), request=request
    )
    db.commit()

    settings = get_settings()
    set_auth_cookies(response, user_id=user.id, role=user.role.value, settings=settings)
    return user


@router.post("/refresh", response_model=MeResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    settings = get_settings()
    try:
        payload = decode_token(token, settings=settings, expected_type="refresh")
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session") from exc

    user = db.get(User, uuid.UUID(payload["sub"]))
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")

    set_auth_cookies(response, user_id=user.id, role=user.role.value, settings=settings)
    return user


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    clear_auth_cookies(response)


@router.get("/me", response_model=MeResponse)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest, db: Session = Depends(get_db)
) -> dict[str, str]:
    # Always return 202 regardless of whether the email exists, so this endpoint
    # can't be used to enumerate accounts (matches the frontend's copy either way).
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if user is not None and user.is_active:
        raw_token = secrets.token_urlsafe(32)
        db.add(
            PasswordResetToken(
                user_id=user.id,
                token_hash=hashlib.sha256(raw_token.encode()).hexdigest(),
                expires_at=datetime.now(UTC) + RESET_TOKEN_TTL,
            )
        )
        db.commit()
        # No email service configured yet (docs/decisions) — log the link so a dev/admin
        # can hand it to the user out of band until ADM settings grow an SMTP config.
        logger.info("Password reset link for %s: /reset-password?token=%s", user.email, raw_token)
    return {"status": "accepted"}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)) -> None:
    token_hash = hashlib.sha256(payload.token.encode()).hexdigest()
    reset_token = (
        db.query(PasswordResetToken)
        .filter(PasswordResetToken.token_hash == token_hash)
        .one_or_none()
    )
    now = datetime.now(UTC)
    if (
        reset_token is None
        or reset_token.used_at is not None
        or reset_token.expires_at.replace(tzinfo=UTC) < now
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    user = db.get(User, reset_token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    user.password_hash = hash_password(payload.password)
    reset_token.used_at = now
    db.commit()
