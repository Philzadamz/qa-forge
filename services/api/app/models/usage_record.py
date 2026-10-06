import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, utcnow


class UsageRecord(IdMixin, Base):
    """One AI call site's token spend (PRD §12 "token usage"; Phase 8 usage dashboard).

    `feature` identifies the call site ("story_generation", "api_case_generation",
    "report_draft", "execution_run"), `entity_id` the row it was spent on (job/suite/report/run
    id) so usage can be traced back to what produced it.
    """

    __tablename__ = "usage_records"

    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id"), index=True, default=None
    )
    feature: Mapped[str] = mapped_column(String(50), index=True)
    entity_id: Mapped[str | None] = mapped_column(String(100), default=None)
    model: Mapped[str] = mapped_column(String(100))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
