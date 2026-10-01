import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import GenerationJobStatus
from app.db.base import Base, IdMixin, JsonType, TimestampMixin


class GenerationJob(IdMixin, TimestampMixin, Base):
    __tablename__ = "generation_jobs"

    suite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_suites.id"), index=True)
    story_ids: Mapped[list[str]] = mapped_column(JsonType, default=list)
    status: Mapped[GenerationJobStatus] = mapped_column(
        SAEnum(GenerationJobStatus, native_enum=False, length=20),
        default=GenerationJobStatus.QUEUED,
    )
    model: Mapped[str] = mapped_column(String(100))
    prompt_version: Mapped[str] = mapped_column(String(20))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_estimate: Mapped[float] = mapped_column(default=0.0)
    error: Mapped[str | None] = mapped_column(String(2000), default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
