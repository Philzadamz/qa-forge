import pytest
from cryptography.fernet import InvalidToken

from app.core.config import Settings
from app.core.crypto import decrypt_secret, encrypt_secret


def test_roundtrip_with_explicit_key() -> None:
    from cryptography.fernet import Fernet

    settings = Settings(secrets_key=Fernet.generate_key().decode(), jwt_secret="x" * 32)
    ciphertext = encrypt_secret("hunter2", settings)
    assert ciphertext != "hunter2"
    assert decrypt_secret(ciphertext, settings) == "hunter2"


def test_roundtrip_with_dev_fallback_key() -> None:
    settings = Settings(secrets_key=None, jwt_secret="some-dev-jwt-secret")
    ciphertext = encrypt_secret("hunter2", settings)
    assert decrypt_secret(ciphertext, settings) == "hunter2"


def test_dev_fallback_key_is_deterministic_per_jwt_secret() -> None:
    settings_a = Settings(secrets_key=None, jwt_secret="same-secret")
    settings_b = Settings(secrets_key=None, jwt_secret="same-secret")
    ciphertext = encrypt_secret("hunter2", settings_a)
    assert decrypt_secret(ciphertext, settings_b) == "hunter2"


def test_different_jwt_secrets_cannot_decrypt_each_other() -> None:
    settings_a = Settings(secrets_key=None, jwt_secret="secret-a")
    settings_b = Settings(secrets_key=None, jwt_secret="secret-b")
    ciphertext = encrypt_secret("hunter2", settings_a)
    with pytest.raises(InvalidToken):
        decrypt_secret(ciphertext, settings_b)
