from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, JsonType, TimestampMixin


class ReportDefaults(IdMixin, TimestampMixin, Base):
    """Singleton-ish admin settings row (ADM-RD-1..3) — the app reads whichever row exists;
    the seed/admin UI never creates more than one."""

    __tablename__ = "report_defaults"

    exit_criteria: Mapped[list[str]] = mapped_column(JsonType, default=list)
    approval_roles: Mapped[list[dict[str, object]]] = mapped_column(JsonType, default=list)
    classification_label: Mapped[str] = mapped_column(String(50), default="Public")
    organisation_name: Mapped[str] = mapped_column(String(200), default="")
