import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import BugStatus, Severity
from app.db.base import Base, IdMixin, TimestampMixin


class Bug(IdMixin, TimestampMixin, Base):
    __tablename__ = "bugs"

    suite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_suites.id"), index=True)
    test_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_cases.id"), default=None
    )
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(String(4000), default="")
    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, native_enum=False, length=20), default=Severity.MEDIUM
    )
    status: Mapped[BugStatus] = mapped_column(
        SAEnum(BugStatus, native_enum=False, length=20), default=BugStatus.OPEN
    )
    external_link: Mapped[str | None] = mapped_column(String(500), default=None)
