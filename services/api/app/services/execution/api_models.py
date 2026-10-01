"""Shared schemas for the API runner (PRD §7.6.2): the endpoint catalogue a parsed spec
produces, and the executable request plan an AI-generated (or future manually-authored) API
test case compiles down to. Both the generation call and the runner import these."""

from typing import Literal

from pydantic import BaseModel, Field

AssertionKind = Literal[
    "status_equals",
    "json_path_equals",
    "json_path_contains",
    "json_path_matches",
    "schema_valid",
    "header_present",
    "latency_below_ms",
]

ApiCategory = Literal[
    "happy_path",
    "required_field_missing",
    "invalid_type_format",
    "boundary_value",
    "auth_missing_invalid_expired",
    "permission_idor",
    "idempotency",
    "pagination_filtering",
    "schema_conformance",
    "error_message_format",
    "response_time",
]


class AssertionSpec(BaseModel):
    kind: AssertionKind
    path: str | None = None  # JSON path (dot notation) or header name, depending on kind
    # Scalar for most kinds; a JSON Schema object for "schema_valid"; an int/float threshold
    # (milliseconds) for "latency_below_ms".
    expected: object | None = None


class RequestPlan(BaseModel):
    """Compiled executable request (PRD §7.6.2 step 3). `path`, header values, query values,
    and string body values may contain `{{var}}` placeholders substituted at run time from
    earlier requests' `extract`ed values, enabling chained flows (create -> get -> update)."""

    method: Literal["GET", "POST", "PUT", "PATCH", "DELETE"]
    path: str
    headers: dict[str, str] = Field(default_factory=dict)
    query: dict[str, str] = Field(default_factory=dict)
    body: dict[str, object] | None = None
    extract: dict[str, str] = Field(default_factory=dict)  # var_name -> response JSON path
    assertions: list[AssertionSpec] = Field(default_factory=list)


class ApiCaseDraft(BaseModel):
    feature: str
    scenario: str
    steps: list[str] = Field(min_length=1)
    expected_result: str
    category: ApiCategory
    priority: Literal["P1", "P2", "P3", "P4"] = "P2"
    request_plan: RequestPlan


class ApiCaseDraftList(BaseModel):
    cases: list[ApiCaseDraft]


class EndpointParam(BaseModel):
    name: str
    location: Literal["path", "query", "header"]
    required: bool = False
    schema_type: str = "string"


class EndpointInfo(BaseModel):
    method: str
    path: str
    summary: str = ""
    parameters: list[EndpointParam] = Field(default_factory=list)
    request_body_schema: dict[str, object] | None = None
    response_schemas: dict[str, dict[str, object]] = Field(default_factory=dict)


class EndpointCatalogue(BaseModel):
    base_url: str | None = None
    endpoints: list[EndpointInfo]
