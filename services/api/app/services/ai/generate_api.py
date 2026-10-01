"""AI generation of API test cases + their executable request plans (PRD §7.6.2 steps 1-3) —
one call per selected endpoint, same pattern as `generate.py`'s one-call-per-feature."""

import json

from app.services.ai.client import LLMClient
from app.services.ai.prompts import load_prompt
from app.services.ai.structured import call_structured
from app.services.execution.api_models import ApiCaseDraft, ApiCaseDraftList, EndpointInfo

PROMPT_VERSION = "v1"


def generate_api_cases(
    client: LLMClient,
    *,
    endpoint: EndpointInfo,
    guidance: str = "",
    auth_header_template: str | None = None,
    model: str,
    temperature: float = 0.2,
) -> list[ApiCaseDraft]:
    system = load_prompt("generate_api_cases", PROMPT_VERSION)
    context = {
        "method": endpoint.method,
        "path": endpoint.path,
        "summary": endpoint.summary,
        "parameters": [p.model_dump() for p in endpoint.parameters],
        "request_body_schema": endpoint.request_body_schema,
        "response_schemas": endpoint.response_schemas,
    }
    if auth_header_template:
        context["auth_header_template"] = (
            f"When a case needs a valid Authorization header, use exactly: "
            f"{auth_header_template!r} (a placeholder the runner resolves itself)."
        )
    user_parts = [f"Endpoint:\n{json.dumps(context, default=str)}"]
    if guidance.strip():
        user_parts.append(f"Guidance from the QA engineer:\n{guidance.strip()}")
    user = "\n\n".join(user_parts)

    result = call_structured(
        client,
        system=system,
        user=user,
        schema=ApiCaseDraftList,
        model=model,
        temperature=temperature,
    )
    return result.cases
