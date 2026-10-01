import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import SuiteStatus
from app.db.base import Base, IdMixin, JsonType, TimestampMixin


class TestSuite(IdMixin, TimestampMixin, Base):
    __test__ = False  # not a pytest test class, despite the name
    __tablename__ = "test_suites"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_case_types.id"))
    name: Mapped[str] = mapped_column(String(300))
    status: Mapped[SuiteStatus] = mapped_column(
        SAEnum(SuiteStatus, native_enum=False, length=20), default=SuiteStatus.DRAFT
    )
    story_ids: Mapped[list[str]] = mapped_column(JsonType, default=list)
    header_json: Mapped[dict[str, object]] = mapped_column(JsonType, default=dict)
    # Snapshot of the type's default cases at creation time (ADM-DC-6) — later admin edits to
    # the defaults library don't silently change an in-progress suite.
    default_version_snapshot: Mapped[dict[str, object]] = mapped_column(JsonType, default=dict)
    template_xlsx_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("templates.id"), default=None
    )
    template_docx_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("templates.id"), default=None
    )
    test_cycle: Mapped[int] = mapped_column(Integer, default=1)
