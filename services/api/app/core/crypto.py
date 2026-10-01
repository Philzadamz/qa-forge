"""Symmetric encryption for the `secrets` table (PRD §5, §7.6 — "secrets by reference").

`Settings.secrets_key` should be a real Fernet key in any shared environment. In local dev,
where no `.env` value is required to get started (docs/decisions/001), we derive a
deterministic key from `jwt_secret` instead of failing startup — fine for throwaway local
data, never used once a real `SECRETS_KEY` is set.
"""

import base64
import hashlib
from functools import lru_cache

from cryptography.fernet import Fernet

from app.core.config import Settings


def _derive_dev_key(jwt_secret: str) -> bytes:
    digest = hashlib.sha256(jwt_secret.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache
def _fernet_for(secrets_key: str | None, jwt_secret: str) -> Fernet:
    key = secrets_key.encode("utf-8") if secrets_key else _derive_dev_key(jwt_secret)
    return Fernet(key)


def get_fernet(settings: Settings) -> Fernet:
    return _fernet_for(settings.secrets_key, settings.jwt_secret)


def encrypt_secret(value: str, settings: Settings) -> str:
    return get_fernet(settings).encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str, settings: Settings) -> str:
    return get_fernet(settings).decrypt(ciphertext.encode("ascii")).decode("utf-8")
