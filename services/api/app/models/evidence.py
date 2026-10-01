import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import EvidenceKind
from app.db.base import Base, IdMixin, TimestampMixin


class Evidence(IdMixin, TimestampMixin, Base):
    __tablename__ = "evidence"

    test_case_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_cases.id"), index=True)
    run_id: Mapped[uuid.UUID | None] = mapped_column(default=None)  # test_runs lands in Phase 5
    kind: Mapped[EvidenceKind] = mapped_column(
        SAEnum(EvidenceKind, native_enum=False, length=20), default=EvidenceKind.SCREENSHOT
    )
    file_key: Mapped[str] = mapped_column(String(500))
    caption: Mapped[str | None] = mapped_column(String(300), default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
