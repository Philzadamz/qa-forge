import uuid

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, IdMixin, TimestampMixin


class Apk(IdMixin, TimestampMixin, Base):
    """An uploaded, analyzed APK (PRD §7.6.3, §10 `POST /apks`). Analysis
    (`services/execution/apk_analysis.py`) runs once at upload time via `aapt dump badging` —
    the extracted package/activity/version are shown to the user for confirmation before any
    run references this row, per the PRD's "shown for confirmation" requirement."""

    __tablename__ = "apks"

    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    file_key: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(300))
    file_size: Mapped[int] = mapped_column(Integer)
    package_name: Mapped[str] = mapped_column(String(300))
    launch_activity: Mapped[str] = mapped_column(String(300))
    version_name: Mapped[str] = mapped_column(String(100), default="")
    version_code: Mapped[str] = mapped_column(String(50), default="")
    label: Mapped[str] = mapped_column(String(200), default="")
