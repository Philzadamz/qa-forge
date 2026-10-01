import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    app_code: str = Field(min_length=1, max_length=50)
    id_prefix: str = Field(min_length=1, max_length=50)
    user_group_dept: str | None = None
    solution_provider: str | None = None
    developers: list[str] = Field(default_factory=list)
    reviewed_by: str | None = None
    default_test_url: str | None = None
    members: list[uuid.UUID] = Field(default_factory=list)
    approvers: dict[str, object] = Field(default_factory=dict)


class ProjectPatch(BaseModel):
    name: str | None = None
    app_code: str | None = None
    id_prefix: str | None = None
    user_group_dept: str | None = None
    solution_provider: str | None = None
    developers: list[str] | None = None
    reviewed_by: str | None = None
    default_test_url: str | None = None
    members: list[uuid.UUID] | None = None
    approvers: dict[str, object] | None = None
    owner_id: uuid.UUID | None = None  # admin-only reassignment (ADM-UP-2)


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    app_code: str
    id_prefix: str
    user_group_dept: str | None
    solution_provider: str | None
    developers: list[str]
    reviewed_by: str | None
    default_test_url: str | None
    owner_id: uuid.UUID
    members: list[str]
    approvers: dict[str, object]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
