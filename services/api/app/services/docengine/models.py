"""Plain dataclasses for document-engine inputs — deliberately not Pydantic.

These are internal rendering inputs, not API request/response bodies (which do use Pydantic
per CLAUDE.md). Keeping the writers decoupled from the API schemas lets them be exercised
directly with fixture data (PRD §13.4), independent of the suite/generation pipeline that
will eventually construct these objects in Phase 3/4.
"""

from dataclasses import dataclass, field
from pathlib import Path

from app.core.enums import TestStatus


@dataclass
class EvidenceImage:
    file_path: Path
    caption: str | None = None


@dataclass
class ExportCase:
    case_no: str  # pre-numbered, e.g. "Kusala_001" — numbering is the caller's job
    feature: str
    scenario: str
    steps: list[str]
    expected_result: str
    actual_result: str
    status: TestStatus
    evidence_group: str = "Default Scenarios"
    is_regression: bool = False
    evidence: list[EvidenceImage] = field(default_factory=list)


@dataclass
class SuiteHeader:
    project_name_line: str  # "<APPCODE>: <Suite name>"
    user_group_dept: str
    solution_provider: str
    developers: str  # comma-separated
    test_done_by: str
    test_reviewed_by: str
    start_date: str  # DD/MM/YYYY
    end_date: str
    test_description: str
    endpoint_url: str


@dataclass
class SuiteExportData:
    header: SuiteHeader
    default_cases: list[ExportCase] = field(default_factory=list)
    functional_cases: list[ExportCase] = field(default_factory=list)


@dataclass
class FeatureRow:
    name: str
    description: str
    implemented: bool = True
    functional: bool = True


@dataclass
class ExceptionRow:
    case_id: str
    status_type: str
    description: str
    severity: str
    risk: str


@dataclass
class ApprovalRow:
    action: str
    name: str
    staff_id: str
    signature: str = ""
    date: str = ""


@dataclass
class ResultAnalysis:
    test_cycles: int
    total: int
    passed: int
    failed: int
    unexecuted: int
    suspended: int
    modification: int


@dataclass
class BugsSummary:
    raised: int = 0
    fixed_retested: int = 0
    open: int = 0


@dataclass
class ReportData:
    product_name: str
    pr_links: list[str]
    version_numbers: list[str]
    test_url: str
    workitem_url: str
    jira_link: str
    general_description: str
    certified: bool
    features: list[FeatureRow]
    exit_criteria: list[str]
    result_analysis: ResultAnalysis
    automation_ratio: str
    bugs: BugsSummary
    exceptions: list[ExceptionRow] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    approvals: list[ApprovalRow] = field(default_factory=list)
    classification_label: str = "Public"
