"""Call 2 of the generation pipeline (PRD §8.2 step 3): functional cases, one call per
feature, run with bounded concurrency by the caller."""

import json

from app.services.ai.client import LLMClient
from app.services.ai.prompts import load_prompt
from app.services.ai.schemas import FunctionalCase, FunctionalCaseList, StoryAnalysis
from app.services.ai.structured import call_structured

PROMPT_VERSION = "v1"

CoverageDepth = str  # "Essential" | "Standard" | "Exhaustive"


def generate_functional_cases(
    client: LLMClient,
    *,
    feature: str,
    analysis: StoryAnalysis,
    coverage_depth: CoverageDepth = "Standard",
    focus_areas: list[str] | None = None,
    style_guide: str = "",
    exemplars: list[dict[str, object]] | None = None,
    default_scenario_summaries: list[str] | None = None,
    model: str,
    temperature: float = 0.2,
) -> list[FunctionalCase]:
    system = load_prompt("generate_functional_cases", PROMPT_VERSION)
    if style_guide.strip():
        system = f"{system}\n\nTeam style guide:\n{style_guide.strip()}"

    context = {
        "feature": feature,
        "coverage_depth": coverage_depth,
        "focus_areas": focus_areas or [],
        "acceptance_criteria": [
            ac.model_dump() for ac in analysis.acceptance_criteria if ac.feature == feature
        ]
        or [ac.model_dump() for ac in analysis.acceptance_criteria],
        "actors": analysis.actors,
        "business_rules": analysis.business_rules,
        "limits": [limit.model_dump(mode="json") for limit in analysis.limits],
        "states": analysis.states,
        "approval_chains": analysis.approval_chains,
        "validations": analysis.validations,
    }
    if exemplars:
        context["exemplars"] = exemplars
    if default_scenario_summaries:
        context["avoid_duplicating_these_default_scenarios"] = default_scenario_summaries

    context_json = json.dumps(context, default=str)
    user = f"Write functional test cases for the feature: {feature}\n\nContext:\n{context_json}"

    result = call_structured(
        client,
        system=system,
        user=user,
        schema=FunctionalCaseList,
        model=model,
        temperature=temperature,
    )
    return result.cases
