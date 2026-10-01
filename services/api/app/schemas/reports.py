import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ReportOut(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID
    fields_json: dict[str, object]
    version: int
    created_at: datetime

    model_config = {"from_attributes": True}


class ReportUpdate(BaseModel):
    """The user edits the AI draft freely — validated against `ReportRenderData` only at
    render time, so a partially-filled-in draft can still be saved along the way."""

    fields_json: dict[str, object]


# --- Render-time validation (mirrors app.services.docengine.models.ReportData) -------------
# A Report's `fields_json` is a loose dict while being edited; this is what it must satisfy
# before `POST /reports/{id}/render` will actually produce a docx.


class FeatureRowIn(BaseModel):
    name: str
    description: str
    implemented: bool = True
    functional: bool = True


class ExceptionRowIn(BaseModel):
    case_id: str
    status_type: str
    description: str
    severity: str
    risk: str


class ApprovalRowIn(BaseModel):
    action: str
    name: str = ""
    staff_id: str = ""
    signature: str = ""
    date: str = ""


class ResultAnalysisIn(BaseModel):
    test_cycles: int
    total: int
    passed: int
    failed: int
    unexecuted: int
    suspended: int
    modification: int


class BugsSummaryIn(BaseModel):
    raised: int = 0
    fixed_retested: int = 0
    open: int = 0


class ReportRenderData(BaseModel):
    product_name: str
    pr_links: list[str] = Field(default_factory=list)
    version_numbers: list[str] = Field(default_factory=list)
    test_url: str = ""
    workitem_url: str = ""
    jira_link: str = ""
    general_description: str = ""
    certified: bool = False
    features: list[FeatureRowIn] = Field(default_factory=list)
    exit_criteria: list[str] = Field(default_factory=list)
    result_analysis: ResultAnalysisIn
    automation_ratio: str = "0:100"
    bugs: BugsSummaryIn = Field(default_factory=BugsSummaryIn)
    exceptions: list[ExceptionRowIn] = Field(default_factory=list)
    comments: list[str] = Field(default_factory=list)
    approvals: list[ApprovalRowIn] = Field(default_factory=list)
    classification_label: str = "Public"

    # Result Analysis override (PRD §7.5 USR-RP-1): if set, the render endpoint trusts these
    # numbers instead of recomputing from the suite's current cases.
    ra_overridden: bool = False
    ra_override_reason: str | None = None
