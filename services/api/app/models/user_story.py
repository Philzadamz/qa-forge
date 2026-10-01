import uuid

from sqlalchemy import Enum as SAEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import StorySource
from app.db.base import Base, IdMixin, JsonType, TimestampMixin


class UserStory(IdMixin, TimestampMixin, Base):
    __tablename__ = "user_stories"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(300))
    source: Mapped[StorySource] = mapped_column(SAEnum(StorySource, native_enum=False, length=20))
    file_key: Mapped[str | None] = mapped_column(String(500), default=None)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    acceptance_criteria: Mapped[list[dict[str, object]]] = mapped_column(JsonType, default=list)
    # Full StoryAnalysis JSON, cached so re-opening a suite doesn't re-run the analysis call
    # (PRD's cost-overrun mitigation: "caching of story analysis").
    analysis_json: Mapped[dict[str, object] | None] = mapped_column(JsonType, default=None)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
