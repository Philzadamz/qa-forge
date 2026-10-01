import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import RunStatus, RunStepOutcome, RunTarget
from app.db.base import Base, IdMixin, JsonType, TimestampMixin


class TestRun(IdMixin, TimestampMixin, Base):
    __test__ = False  # not a pytest test class, despite the name
    __tablename__ = "test_runs"

    suite_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("test_suites.id"), default=None)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), index=True)
    target: Mapped[RunTarget] = mapped_column(SAEnum(RunTarget, native_enum=False, length=10))
    status: Mapped[RunStatus] = mapped_column(
        SAEnum(RunStatus, native_enum=False, length=20), default=RunStatus.QUEUED
    )
    # Secrets referenced by id only (`secret_ref`) — never a plaintext value (PRD §7.6.1).
    config_json: Mapped[dict[str, object]] = mapped_column(JsonType, default=dict)
    guidance_text: Mapped[str] = mapped_column(String(4000), default="")
    selected_case_ids: Mapped[list[str]] = mapped_column(JsonType, default=list)
    worker_id: Mapped[str | None] = mapped_column(String(100), default=None)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    summary_json: Mapped[dict[str, object]] = mapped_column(JsonType, default=dict)
    error: Mapped[str | None] = mapped_column(String(2000), default=None)


class RunStep(IdMixin, TimestampMixin, Base):
    __tablename__ = "run_steps"

    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_runs.id"), index=True)
    test_case_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("test_cases.id"), default=None
    )
    seq: Mapped[int] = mapped_column(Integer)
    action: Mapped[str] = mapped_column(String(100))
    target: Mapped[str | None] = mapped_column(String(500), default=None)
    input_masked: Mapped[str | None] = mapped_column(String(1000), default=None)
    assertion: Mapped[str | None] = mapped_column(String(500), default=None)
    outcome: Mapped[RunStepOutcome] = mapped_column(
        SAEnum(RunStepOutcome, native_enum=False, length=10), default=RunStepOutcome.PASS
    )
    message: Mapped[str | None] = mapped_column(String(2000), default=None)
    screenshot_evidence_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("evidence.id"), default=None
    )
    duration_ms: Mapped[int | None] = mapped_column(Integer, default=None)
