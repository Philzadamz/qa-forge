"""Call: draft the narrative sections of a QA Test Completion Report (PRD §8.3)."""

import json

from app.services.ai.client import LLMClient
from app.services.ai.prompts import load_prompt
from app.services.ai.schemas import ReportDraft
from app.services.ai.structured import call_structured

PROMPT_VERSION = "v1"


def draft_report(
    client: LLMClient,
    *,
    product_name: str,
    features: list[str],
    non_passed_cases: list[dict[str, object]],
    bugs: list[dict[str, object]],
    pass_rate: float,
    model: str,
    temperature: float = 0.2,
) -> ReportDraft:
    system = load_prompt("draft_report", PROMPT_VERSION)
    context = {
        "product_name": product_name,
        "features": features,
        "non_passed_cases": non_passed_cases,
        "bugs": bugs,
        "pass_rate_percent": round(pass_rate * 100, 1),
    }
    user = f"Draft the report sections from this suite data:\n{json.dumps(context, default=str)}"

    return call_structured(
        client, system=system, user=user, schema=ReportDraft, model=model, temperature=temperature
    )
