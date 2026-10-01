import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import SecretKind


class SecretIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    value: str = Field(min_length=1, max_length=2000)
    kind: SecretKind = SecretKind.PASSWORD


class SecretOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    kind: SecretKind
    created_at: datetime
