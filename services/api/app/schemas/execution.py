import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import BugStatus, EvidenceKind, Severity


class EvidenceOut(BaseModel):
    id: uuid.UUID
    test_case_id: uuid.UUID
    kind: EvidenceKind
    caption: str | None
    sort_order: int
    created_at: datetime

    model_config = {"from_attributes": True}


class BugIn(BaseModel):
    test_case_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=300)
    description: str = ""
    severity: Severity = Severity.MEDIUM
    status: BugStatus = BugStatus.OPEN
    external_link: str | None = None


class BugPatch(BaseModel):
    title: str | None = None
    description: str | None = None
    severity: Severity | None = None
    status: BugStatus | None = None
    external_link: str | None = None


class BugOut(BaseModel):
    id: uuid.UUID
    suite_id: uuid.UUID
    test_case_id: uuid.UUID | None
    title: str
    description: str
    severity: Severity
    status: BugStatus
    external_link: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
