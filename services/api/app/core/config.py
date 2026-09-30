"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: Literal["dev", "test", "prod"] = "dev"
    log_level: str = "INFO"
    api_prefix: str = "/api/v1"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Database: SQLite for local dev without Docker (see docs/decisions/001), Postgres otherwise.
    database_url: str = f"sqlite:///{(REPO_ROOT / 'var' / 'qa_forge.db').as_posix()}"

    # Object storage: "local" writes under storage_local_root; "s3" targets MinIO/S3.
    storage_backend: Literal["local", "s3"] = "local"
    storage_local_root: Path = REPO_ROOT / "var" / "storage"
    s3_endpoint_url: str | None = None
    s3_bucket: str = "qa-forge"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None

    # Queue: empty means run jobs in-process (dev without Redis).
    redis_url: str | None = None

    # Auth
    jwt_secret: str = "change-me-in-env"  # noqa: S105 - overridden via env outside dev
    access_token_minutes: int = 15
    refresh_token_days: int = 7

    # Encryption key for the secrets table (Fernet, urlsafe base64, 32 bytes).
    secrets_key: str | None = None

    templates_dir: Path = REPO_ROOT / "templates"


@lru_cache
def get_settings() -> Settings:
    return Settings()
