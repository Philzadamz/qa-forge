import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import RunStatus, RunStepOutcome, RunTarget


class RunCreate(BaseModel):
    suite_id: uuid.UUID
    case_ids: list[uuid.UUID] = Field(min_length=1)
    target: RunTarget = RunTarget.WEB
    target_url: str | None = None  # Web: the page URL. API: the base URL.
    guidance_text: str = ""
    force_agent: bool = False
    self_heal: bool = True
    default_headers: dict[str, str] = Field(default_factory=dict)
    env_vars: dict[str, str] = Field(default_factory=dict)


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    suite_id: uuid.UUID | None
    project_id: uuid.UUID
    target: RunTarget
    status: RunStatus
    config_json: dict[str, object]
    guidance_text: str
    selected_case_ids: list[str]
    started_at: datetime | None
    finished_at: datetime | None
    summary_json: dict[str, object]
    error: str | None
    created_at: datetime


class RunStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    test_case_id: uuid.UUID | None
    seq: int
    action: str
    target: str | None
    input_masked: str | None
    assertion: str | None
    outcome: RunStepOutcome
    message: str | None
    screenshot_evidence_id: uuid.UUID | None
    duration_ms: int | None


class RunApplyIn(BaseModel):
    case_ids: list[uuid.UUID] | None = None
