import uuid

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, JsonType, SoftDeleteMixin, TimestampMixin


class Project(IdMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200))
    app_code: Mapped[str] = mapped_column(String(50))
    id_prefix: Mapped[str] = mapped_column(String(50))
    user_group_dept: Mapped[str | None] = mapped_column(String(200), default=None)
    solution_provider: Mapped[str | None] = mapped_column(String(200), default=None)
    developers: Mapped[list[str]] = mapped_column(JsonType, default=list)
    reviewed_by: Mapped[str | None] = mapped_column(String(200), default=None)
    default_test_url: Mapped[str | None] = mapped_column(String(500), default=None)
    # Owner is the primary RBAC boundary ("sees only projects they own or are members of",
    # PRD §7.1); members supplements it for shared access without transferring ownership.
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    members: Mapped[list[str]] = mapped_column(JsonType, default=list)  # user id strings
    approvers: Mapped[dict[str, object]] = mapped_column(JsonType, default=dict)
