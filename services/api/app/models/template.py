import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import TemplateKind, TemplateStatus
from app.db.base import Base, IdMixin, TimestampMixin


class Template(IdMixin, TimestampMixin, Base):
    __tablename__ = "templates"

    kind: Mapped[TemplateKind] = mapped_column(SAEnum(TemplateKind, native_enum=False, length=20))
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    file_key: Mapped[str] = mapped_column(String(500))  # raw uploaded file, as given
    rendered_key: Mapped[str | None] = mapped_column(String(500), default=None)
    # docx templates are auto-tokenized on upload (ADM-TM-2); rendered_key points at that
    # working copy. xlsx templates are used as-is, so rendered_key == file_key for them.
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_case_types.id"), default=None
    )
    status: Mapped[TemplateStatus] = mapped_column(
        SAEnum(TemplateStatus, native_enum=False, length=20), default=TemplateStatus.DRAFT
    )
    validation_error: Mapped[str | None] = mapped_column(String(2000), default=None)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"), default=None)
    notes: Mapped[str | None] = mapped_column(String(2000), default=None)
