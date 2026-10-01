import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, IdMixin, JsonType, TimestampMixin


class TestCaseType(IdMixin, TimestampMixin, Base):
    __test__ = False  # not a pytest test class, despite the name (PRD §5 domain model)
    __tablename__ = "test_case_types"

    name: Mapped[str] = mapped_column(String(200), unique=True)
    description: Mapped[str | None] = mapped_column(String(2000), default=None)
    id_prefix_hint: Mapped[str | None] = mapped_column(String(50), default=None)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    defaults: Mapped[list["DefaultTestCase"]] = relationship(
        back_populates="type", cascade="all, delete-orphan", order_by="DefaultTestCase.sort_order"
    )


class DefaultTestCase(IdMixin, TimestampMixin, Base):
    __tablename__ = "default_test_cases"

    type_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_case_types.id"), index=True)
    feature: Mapped[str] = mapped_column(String(300))
    scenario: Mapped[str] = mapped_column(String(2000))
    steps: Mapped[list[str]] = mapped_column(JsonType, default=list)
    expected_result: Mapped[str] = mapped_column(String(2000))
    default_actual_result: Mapped[str] = mapped_column(String(500), default="As expected")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    evidence_group: Mapped[str] = mapped_column(String(100), default="Default Scenarios")
    tags: Mapped[list[str]] = mapped_column(JsonType, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    version: Mapped[int] = mapped_column(Integer, default=1)

    type: Mapped[TestCaseType] = relationship(back_populates="defaults")
