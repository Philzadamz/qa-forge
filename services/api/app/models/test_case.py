import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import (
    CaseSection,
    CaseSource,
    ExecutionMode,
    Priority,
    TestStatus,
)
from app.db.base import Base, IdMixin, JsonType, TimestampMixin


class TestCase(IdMixin, TimestampMixin, Base):
    __test__ = False  # not a pytest test class, despite the name
    __tablename__ = "test_cases"

    suite_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_suites.id"), index=True)
    section: Mapped[CaseSection] = mapped_column(SAEnum(CaseSection, native_enum=False, length=20))
    case_no: Mapped[int] = mapped_column(Integer)
    display_id: Mapped[str] = mapped_column(String(50))
    feature: Mapped[str] = mapped_column(String(300))
    scenario: Mapped[str] = mapped_column(String(2000))
    steps: Mapped[list[str]] = mapped_column(JsonType, default=list)
    expected_result: Mapped[str] = mapped_column(String(2000))
    actual_result: Mapped[str] = mapped_column(String(2000), default="")
    status: Mapped[TestStatus] = mapped_column(
        SAEnum(TestStatus, native_enum=False, length=20), default=TestStatus.NOT_TESTED
    )
    is_regression: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_group: Mapped[str] = mapped_column(String(100), default="Default Scenarios")
    priority: Mapped[Priority] = mapped_column(
        SAEnum(Priority, native_enum=False, length=10), default=Priority.P2
    )
    technique: Mapped[list[str]] = mapped_column(JsonType, default=list)
    traces_to: Mapped[list[str]] = mapped_column(JsonType, default=list)
    source: Mapped[CaseSource] = mapped_column(SAEnum(CaseSource, native_enum=False, length=20))
    default_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("default_test_cases.id"), default=None
    )
    included: Mapped[bool] = mapped_column(Boolean, default=True)
    # Flagged by post-generation dedup (PRD §7.3 "Duplicate check") — hidden by default in
    # the UI, not deleted, so the user can still promote it back if the flag is wrong.
    is_duplicate: Mapped[bool] = mapped_column(Boolean, default=False)
    execution_mode: Mapped[ExecutionMode | None] = mapped_column(
        SAEnum(ExecutionMode, native_enum=False, length=20), default=None
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
