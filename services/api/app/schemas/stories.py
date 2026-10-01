import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import StorySource


class StoryPasteIn(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    text: str = Field(min_length=1)


class StoryOut(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    source: StorySource
    acceptance_criteria: list[dict[str, object]]
    created_at: datetime

    model_config = {"from_attributes": True}


class StoryDetailOut(StoryOut):
    extracted_text: str
