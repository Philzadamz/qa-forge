import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, JsonType, TimestampMixin


class Report(IdMixin, TimestampMixin, Base):
    __tablename__ = "reports"

    suite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_suites.id"), index=True)
    template_docx_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("templates.id"), default=None
    )
    # Full ReportData-shaped dict (PRD Appendix C fields) — editable by the user after the AI
    # draft, re-rendered on demand rather than regenerated from scratch each time.
    fields_json: Mapped[dict[str, object]] = mapped_column(JsonType, default=dict)
    file_key: Mapped[str | None] = mapped_column(String(500), default=None)
    version: Mapped[int] = mapped_column(Integer, default=1)
    generated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
