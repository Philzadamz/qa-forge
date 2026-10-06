"""Call: draft the feature descriptions of a QA Test Completion Report (PRD §8.3)."""

import json

from app.services.ai.client import LLMClient
from app.services.ai.prompts import load_prompt
from app.services.ai.schemas import FeatureDescriptionsDraft
from app.services.ai.structured import call_structured

PROMPT_VERSION = "v2"


def draft_feature_descriptions(
    client: LLMClient,
    *,
    product_name: str,
    features: list[str],
    model: str,
    temperature: float = 0.2,
) -> FeatureDescriptionsDraft:
    system = load_prompt("draft_report", PROMPT_VERSION)
    context = {"product_name": product_name, "features": features}
    user = f"Describe these features of {product_name}:\n{json.dumps(context, default=str)}"
    return call_structured(
        client,
        system=system,
        user=user,
        schema=FeatureDescriptionsDraft,
        model=model,
        temperature=temperature,
    )
