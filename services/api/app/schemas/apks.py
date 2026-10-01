import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ApkOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    file_name: str
    file_size: int
    package_name: str
    launch_activity: str
    version_name: str
    version_code: str
    label: str
    created_at: datetime
