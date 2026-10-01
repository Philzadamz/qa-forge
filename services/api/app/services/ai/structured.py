"""Validated structured calls: one automatic repair retry on invalid JSON (PRD §8.1)."""

import json

from pydantic import BaseModel, ValidationError

from app.services.ai.client import LLMClient, LLMError

REPAIR_INSTRUCTION = """Your previous response was not valid JSON matching the required schema.

Validation errors:
{errors}

Your previous response was:
{previous}

Return ONLY a corrected JSON object matching the schema. No commentary, no markdown fences."""


def call_structured[T: BaseModel](
    client: LLMClient,
    *,
    system: str,
    user: str,
    schema: type[T],
    model: str,
    temperature: float = 0.2,
    max_tokens: int = 8192,
) -> T:
    raw = client.complete_json(
        system=system, user=user, model=model, temperature=temperature, max_tokens=max_tokens
    )
    try:
        return schema.model_validate_json(_strip_fences(raw))
    except (ValidationError, json.JSONDecodeError) as first_error:
        repair_user = REPAIR_INSTRUCTION.format(errors=str(first_error), previous=raw)
        repaired = client.complete_json(
            system=system,
            user=repair_user,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            return schema.model_validate_json(_strip_fences(repaired))
        except (ValidationError, json.JSONDecodeError) as second_error:
            raise LLMError(
                f"Model output did not match {schema.__name__} after a repair retry: {second_error}"
            ) from second_error


def _strip_fences(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()
