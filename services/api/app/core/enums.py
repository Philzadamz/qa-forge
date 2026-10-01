"""Single source of truth for shared enums (PRD §3.3). Reuse these everywhere."""

from enum import StrEnum


class TestStatus(StrEnum):
    __test__ = False  # not a pytest test class, despite the name
    PASSED = "Passed"
    FAILED = "Failed"
    NOT_TESTED = "Not Tested"
    SUSPENDED = "Suspended"
    MODIFICATION = "Modification"
    BLOCKED = "Blocked"


# Default status palette (admin-editable at runtime via app_settings, PRD §3.1 / ADM-EX-3).
DEFAULT_STATUS_PALETTE: dict[TestStatus, dict[str, str]] = {
    TestStatus.PASSED: {"fill": "00B050", "font": "FFFFFF"},
    TestStatus.FAILED: {"fill": "FF0000", "font": "FFFFFF"},
    TestStatus.NOT_TESTED: {"fill": "A6A6A6", "font": "FFFFFF"},
    TestStatus.SUSPENDED: {"fill": "FFC000", "font": "FFFFFF"},
    TestStatus.MODIFICATION: {"fill": "7030A0", "font": "FFFFFF"},
    TestStatus.BLOCKED: {"fill": "C55A11", "font": "FFFFFF"},
}

# Report mapping: Un-executed = Not Tested + Blocked; Modification-Requiring = Modification.
UNEXECUTED_STATUSES: frozenset[TestStatus] = frozenset({TestStatus.NOT_TESTED, TestStatus.BLOCKED})


class Role(StrEnum):
    ADMIN = "admin"
    USER = "user"
    VIEWER = "viewer"


class CaseSection(StrEnum):
    DEFAULT = "default"
    FUNCTIONAL = "functional"


class CaseSource(StrEnum):
    DEFAULT = "default"
    AI = "ai"
    MANUAL = "manual"
    RUN = "run"


class ExecutionMode(StrEnum):
    MANUAL = "manual"
    AUTOMATED = "automated"


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class Severity(StrEnum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"


class RunTarget(StrEnum):
    WEB = "web"
    API = "api"
    ANDROID = "android"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ERROR = "error"
    CANCELLED = "cancelled"


class TemplateKind(StrEnum):
    XLSX_TEST_CASES = "xlsx_test_cases"
    DOCX_REPORT = "docx_report"


class TemplateStatus(StrEnum):
    __test__ = False  # not a pytest test class, despite the name
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class StorySource(StrEnum):
    UPLOAD = "upload"
    PASTE = "paste"
    URL = "url"


class SuiteStatus(StrEnum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    FINAL = "final"


class GenerationJobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class EvidenceKind(StrEnum):
    SCREENSHOT = "screenshot"
    REQUEST_LOG = "request_log"
    VIDEO = "video"
    FILE = "file"


class BugStatus(StrEnum):
    OPEN = "open"
    FIXED = "fixed"
    RETESTED = "retested"
    CLOSED = "closed"


class SecretKind(StrEnum):
    PASSWORD = "password"  # noqa: S105 - enum member value, not a credential
    TOKEN = "token"  # noqa: S105
    API_KEY = "api_key"
    OAUTH_CLIENT = "oauth_client"


class RunStepOutcome(StrEnum):
    PASS = "pass"  # noqa: S105 - enum member value, not a credential
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"
