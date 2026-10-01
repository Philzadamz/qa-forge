import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import SecretKind
from app.db.base import Base, IdMixin, TimestampMixin


class Secret(IdMixin, TimestampMixin, Base):
    """Write-only credential storage for Test Lab runs (PRD §5, §7.6). `ciphertext` is the
    only place the value lives at rest (Fernet, `app/core/crypto.py`) — the API never returns
    plaintext once stored; runs reference a secret by id (`secret_ref`) and the value is
    resolved server-side, immediately before use, never sent to an LLM."""

    __tablename__ = "secrets"
    __table_args__ = (UniqueConstraint("project_id", "name", name="uq_secrets_project_id_name"),)

    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    ciphertext: Mapped[str] = mapped_column(String(2000))
    kind: Mapped[SecretKind] = mapped_column(
        SAEnum(SecretKind, native_enum=False, length=20), default=SecretKind.PASSWORD
    )
