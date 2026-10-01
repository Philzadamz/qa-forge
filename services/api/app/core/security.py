"""Password hashing and JWT access/refresh tokens (PRD §2).

Both tokens are set as httpOnly cookies rather than returned in the response body:
the access token never needs to be readable by client JS (every API call rides on
`credentials: "include"`, see apps/web/src/lib/api.ts), so keeping it out of JS reach
closes off XSS token theft at no cost to the SPA flow.
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import Response

from app.core.config import Settings

_hasher = PasswordHasher()

TokenType = Literal["access", "refresh"]

ACCESS_COOKIE = "qa_forge_access"
REFRESH_COOKIE = "qa_forge_refresh"


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False


def create_token(*, user_id: uuid.UUID, role: str, kind: TokenType, settings: Settings) -> str:
    now = datetime.now(UTC)
    minutes = (
        settings.access_token_minutes if kind == "access" else settings.refresh_token_days * 24 * 60
    )
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": kind,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_token(token: str, *, settings: Settings, expected_type: TokenType) -> dict[str, str]:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if payload.get("type") != expected_type:
        raise jwt.InvalidTokenError(f"Expected a {expected_type} token")
    return payload


def set_auth_cookies(
    response: Response, *, user_id: uuid.UUID, role: str, settings: Settings
) -> None:
    access = create_token(user_id=user_id, role=role, kind="access", settings=settings)
    refresh = create_token(user_id=user_id, role=role, kind="refresh", settings=settings)
    secure = settings.environment == "prod"
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=settings.access_token_minutes * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.refresh_token_days * 24 * 60 * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")
