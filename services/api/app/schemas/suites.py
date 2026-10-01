import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.core.enums import (
    CaseSection,
    CaseSource,
    ExecutionMode,
    GenerationJobStatus,
    Priority,
    SuiteStatus,
    TestStatus,
)

CoverageDepth = Literal["Essential", "Standard", "Exhaustive"]


class SuiteHeaderIn(BaseModel):
    project_name_line: str
    user_group_dept: str = ""
    solution_provider: str = ""
    developers: str = ""
    test_done_by: str = ""
    test_reviewed_by: str = ""
    start_date: str = ""
    end_date: str = ""
    test_description: str = ""
    endpoint_url: str = ""


class SuiteCreate(BaseModel):
    project_id: uuid.UUID
    type_id: uuid.UUID
    name: str = Field(min_length=1, max_length=300)
    story_ids: list[uuid.UUID] = Field(default_factory=list)
    header: SuiteHeaderIn


class SuitePatch(BaseModel):
    name: str | None = None
    status: SuiteStatus | None = None
    story_ids: list[uuid.UUID] | None = None
    header: SuiteHeaderIn | None = None


class SuiteOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    type_id: uuid.UUID
    name: str
    status: SuiteStatus
    story_ids: list[str]
    header_json: dict[str, object]
    test_cycle: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerateRequest(BaseModel):
    story_ids: list[uuid.UUID] = Field(default_factory=list)
    additional_context: str = ""
    coverage_depth: CoverageDepth = "Standard"
    focus_areas: list[str] = Field(default_factory=list)


class JobOut(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID
    status: GenerationJobStatus
    model: str
    prompt_version: str
    input_tokens: int
    output_tokens: int
    error: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class CaseOut(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID
    section: CaseSection
    case_no: int
    display_id: str
    feature: str
    scenario: str
    steps: list[str]
    expected_result: str
    actual_result: str
    status: TestStatus
    is_regression: bool
    evidence_group: str
    priority: Priority
    technique: list[str]
    traces_to: list[str]
    source: CaseSource
    included: bool
    is_duplicate: bool
    execution_mode: ExecutionMode | None
    sort_order: int
    request_plan: dict[str, object] | None = None

    model_config = {"from_attributes": True}


class CaseCreate(BaseModel):
    section: CaseSection
    feature: str = Field(min_length=1, max_length=300)
    scenario: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    evidence_group: str = "Functional Scenarios"
    priority: Priority = Priority.P2
    technique: list[str] = Field(default_factory=list)
    traces_to: list[str] = Field(default_factory=list)


class CasePatch(BaseModel):
    feature: str | None = None
    scenario: str | None = None
    steps: list[str] | None = None
    expected_result: str | None = None
    actual_result: str | None = None
    status: TestStatus | None = None
    is_regression: bool | None = None
    evidence_group: str | None = None
    priority: Priority | None = None
    technique: list[str] | None = None
    traces_to: list[str] | None = None
    included: bool | None = None
    sort_order: int | None = None
    request_plan: dict[str, object] | None = None


class CaseBulkPatch(BaseModel):
    """PRD §7.4 bulk actions — e.g. 'Mark all as Passed / As expected'."""

    case_ids: list[uuid.UUID] = Field(min_length=1)
    status: TestStatus | None = None
    actual_result: str | None = None
    evidence_group: str | None = None
    included: bool | None = None
