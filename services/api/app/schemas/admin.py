import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field

from app.core.enums import Role, TemplateKind, TemplateStatus


class TestCaseTypeIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    id_prefix_hint: str | None = None
    sort_order: int = 0


class TestCaseTypePatch(BaseModel):
    name: str | None = None
    description: str | None = None
    id_prefix_hint: str | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class TestCaseTypeOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    id_prefix_hint: str | None
    sort_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DefaultTestCaseIn(BaseModel):
    feature: str = Field(min_length=1, max_length=300)
    scenario: str = Field(min_length=1)
    steps: list[str] = Field(min_length=1)
    expected_result: str = Field(min_length=1)
    default_actual_result: str = "As expected"
    evidence_group: str = "Default Scenarios"
    tags: list[str] = Field(default_factory=list)
    sort_order: int = 0


class DefaultTestCasePatch(BaseModel):
    feature: str | None = None
    scenario: str | None = None
    steps: list[str] | None = None
    expected_result: str | None = None
    default_actual_result: str | None = None
    evidence_group: str | None = None
    tags: list[str] | None = None
    sort_order: int | None = None
    is_active: bool | None = None


class DefaultTestCaseOut(BaseModel):
    id: uuid.UUID
    type_id: uuid.UUID
    feature: str
    scenario: str
    steps: list[str]
    expected_result: str
    default_actual_result: str
    evidence_group: str
    tags: list[str]
    sort_order: int
    is_active: bool
    version: int

    model_config = {"from_attributes": True}


class ReorderRequest(BaseModel):
    ordered_ids: list[uuid.UUID] = Field(min_length=1)


class ImportWarning(BaseModel):
    row: int | None
    message: str


class ImportPreviewResponse(BaseModel):
    cases: list[DefaultTestCaseIn]
    warnings: list[ImportWarning]


class ImportConfirmRequest(BaseModel):
    cases: list[DefaultTestCaseIn]
    replace_existing: bool = False


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=1, max_length=200)
    staff_id: str | None = None
    role: Role = Role.USER
    password: str = Field(min_length=8)


class UserPatch(BaseModel):
    full_name: str | None = None
    staff_id: str | None = None
    role: Role | None = None
    is_active: bool | None = None


class UserPasswordSet(BaseModel):
    new_password: str = Field(min_length=8)


class TemplateOut(BaseModel):
    id: uuid.UUID
    kind: TemplateKind
    name: str
    version: int
    is_default: bool
    type_id: uuid.UUID | None
    status: TemplateStatus
    validation_error: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApprovalRoleIn(BaseModel):
    action: str = Field(min_length=1, max_length=200)
    default_name: str = ""
    default_staff_id: str = ""


class ReportDefaultsIn(BaseModel):
    exit_criteria: list[str] = Field(default_factory=list)
    approval_roles: list[ApprovalRoleIn] = Field(default_factory=list)
    classification_label: str = "Public"
    organisation_name: str = ""


class ReportDefaultsOut(BaseModel):
    id: uuid.UUID
    exit_criteria: list[str]
    approval_roles: list[dict[str, object]]
    classification_label: str
    organisation_name: str

    model_config = {"from_attributes": True}


class NoteSnippetIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list)


class NoteSnippetPatch(BaseModel):
    title: str | None = None
    body: str | None = None
    tags: list[str] | None = None
    is_active: bool | None = None


class NoteSnippetOut(BaseModel):
    id: uuid.UUID
    title: str
    body: str
    tags: list[str]
    is_active: bool

    model_config = {"from_attributes": True}


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str
    staff_id: str | None
    role: Role
    auth_provider: str
    is_active: bool
    last_login_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}
