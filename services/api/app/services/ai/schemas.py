"""Structured AI I/O schemas (PRD Appendix A). Every AI call is validated against one of
these — invalid output gets one automatic repair retry, then surfaces as an error."""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class Limit(BaseModel):
    subject: str
    value: Decimal
    unit: str
    comparator: Literal["<=", "<", ">=", ">", "=="]
    applies_to: list[str] = Field(default_factory=list)


class AcceptanceCriterion(BaseModel):
    id: str
    text: str
    feature: str


class StoryAnalysis(BaseModel):
    features: list[str]
    actors: list[str]
    acceptance_criteria: list[AcceptanceCriterion]
    business_rules: list[str]
    limits: list[Limit]
    states: list[str]
    approval_chains: list[list[str]]
    validations: list[str]
    integrations: list[str]
    out_of_scope: list[str]
    questions: list[str]


Technique = Literal[
    "happy_path",
    "boundary_value",
    "equivalence_partition",
    "negative",
    "state_transition",
    "role_based",
    "workflow_routing",
    "validation",
    "search_filter",
    "security",
    "usability",
    "integration",
]


class FunctionalCase(BaseModel):
    feature: str
    scenario: str
    steps: list[str] = Field(min_length=1)
    expected_result: str
    priority: Literal["P1", "P2", "P3", "P4"] = "P2"
    techniques: list[Technique] = Field(default_factory=list)
    traces_to: list[str] = Field(default_factory=list)
    evidence_group: str | None = None
    test_data: dict[str, str] = Field(default_factory=dict)


class FunctionalCaseList(BaseModel):
    """Wrapper so `generate` calls return one JSON object, not a bare top-level array
    (some providers' JSON modes require an object at the top level)."""

    cases: list[FunctionalCase] = Field(default_factory=list)


class FeatureDescriptionDraft(BaseModel):
    name: str
    description: str


class ExceptionDraft(BaseModel):
    case_id: str
    status_type: str
    description: str
    severity: Literal["Critical", "High", "Medium", "Low"]
    risk: str


class ReportDraft(BaseModel):
    """PRD §8.3: one call drafts the feature descriptions, exceptions, and comments — the
    numbers (Result Analysis, bugs summary) are computed deterministically, not by the model."""

    feature_descriptions: list[FeatureDescriptionDraft] = Field(default_factory=list)
    exceptions: list[ExceptionDraft] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)


class ExecutionResult(BaseModel):
    status: Literal["Passed", "Failed", "Blocked"]
    actual_result: str
    confidence: float = Field(ge=0, le=1)
    notes: str | None = None
