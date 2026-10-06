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

    # AI (PRD §8, ADM-AI-1). Provider is swappable — DeepSeek for now, Anthropic once a key
    # is available for production (docs/decisions/004) — without touching pipeline code.
    ai_provider: Literal["deepseek", "openai_compatible", "anthropic", "fake"] = "fake"
    deepseek_api_key: str | None = None
    deepseek_base_url: str = "https://api.deepseek.com"
    # Any other OpenAI-compatible gateway (e.g. LLM7 at https://api.llm7.io/v1).
    openai_compatible_api_key: str | None = None
    openai_compatible_base_url: str | None = None
    anthropic_api_key: str | None = None
    ai_model_generation: str = "deepseek-chat"
    ai_model_drafting: str = "deepseek-chat"
    ai_model_light: str = "deepseek-chat"
    ai_temperature: float = 0.2
    ai_max_output_tokens: int = 8192
    # Left at 0 until an operator sets real provider pricing (PRD §12 "token usage"/usage
    # dashboard) — a hardcoded price would silently go stale as providers change rates.
    ai_cost_per_million_input_tokens: float = 0.0
    ai_cost_per_million_output_tokens: float = 0.0

    # Hosts the server may fetch from even though they resolve to a private/loopback address
    # (PRD §12 SSRF allowlist). Empty in production; set for local demo fixtures only.
    ssrf_allowed_hosts: list[str] = Field(default_factory=list)

    # Retention (PRD §12 Privacy): uploads/evidence default 180 days, audit log default 2
    # years. Swept by `python -m app.cli retention-sweep`, run on a schedule by the operator
    # (no in-process scheduler in local mode — docs/decisions/001).
    retention_evidence_days: int = 180
    retention_audit_log_days: int = 730

    # Android runner (PRD §7.6.3). LocalEmulatorProvider targets exactly this AVD — it never
    # touches an emulator instance it wasn't told about, even if other devices are attached.
    android_avd_name: str = "QAForgeTest"
    android_appium_url: str = "http://127.0.0.1:4723"
    android_adb_path: str = "adb"
    android_aapt_path: str = "aapt"
    android_emulator_path: str = "emulator"
    android_boot_timeout_seconds: float = 180.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
