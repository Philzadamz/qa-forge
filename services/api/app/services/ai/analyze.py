"""Call 1 of the generation pipeline (PRD §8.2 step 2): structural analysis of a story."""

from app.services.ai.client import LLMClient
from app.services.ai.prompts import load_prompt
from app.services.ai.schemas import StoryAnalysis
from app.services.ai.structured import call_structured

PROMPT_VERSION = "v1"


def analyze_story(
    client: LLMClient,
    *,
    story_text: str,
    additional_context: str = "",
    model: str,
    temperature: float = 0.2,
) -> StoryAnalysis:
    system = load_prompt("analyze_story", PROMPT_VERSION)
    user_parts = []
    if additional_context.strip():
        user_parts.append(f"Additional context from the QA engineer:\n{additional_context.strip()}")
    user_parts.append(f"User story:\n{story_text}")
    user = "\n\n".join(user_parts)

    return call_structured(
        client, system=system, user=user, schema=StoryAnalysis, model=model, temperature=temperature
    )
