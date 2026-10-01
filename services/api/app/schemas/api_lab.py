import uuid

from pydantic import BaseModel, Field

from app.services.execution.api_models import EndpointCatalogue, EndpointInfo


class CurlParseIn(BaseModel):
    commands: list[str] = Field(min_length=1)


class GenerateApiCasesIn(BaseModel):
    suite_id: uuid.UUID
    endpoints: list[EndpointInfo] = Field(min_length=1)
    guidance: str = ""
    auth_header_template: str | None = None


__all__ = ["CurlParseIn", "EndpointCatalogue", "EndpointInfo", "GenerateApiCasesIn"]
