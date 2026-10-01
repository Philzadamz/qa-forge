from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, JsonType, TimestampMixin


class NoteSnippet(IdMixin, TimestampMixin, Base):
    __tablename__ = "note_snippets"

    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(4000))
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
