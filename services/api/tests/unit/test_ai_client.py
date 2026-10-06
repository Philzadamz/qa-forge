"""Real-world failure (DeepSeek 402 insufficient balance) must surface as LLMError so
callers that degrade gracefully on LLMError (e.g. report drafting) actually do."""

from unittest.mock import MagicMock

import pytest
from openai import APIStatusError

from app.services.ai.client import LLMError, OpenAICompatibleClient


def test_openai_compatible_client_wraps_sdk_errors_as_llm_error() -> None:
    client = OpenAICompatibleClient(api_key="k", base_url="https://example.invalid")
    response = MagicMock(status_code=402, headers={}, request=MagicMock())
    error = APIStatusError(
        "Insufficient Balance",
        response=response,
        body={"error": {"message": "Insufficient Balance"}},
    )
    client._client.chat.completions.create = MagicMock(side_effect=error)  # type: ignore[method-assign]

    with pytest.raises(LLMError, match="Insufficient Balance"):
        client.complete_json(system="sys", user="usr", model="m", temperature=0.2, max_tokens=100)


def test_openai_compatible_client_reports_token_usage_to_the_active_sink() -> None:
    from types import SimpleNamespace

    from app.core import usage

    client = OpenAICompatibleClient(api_key="k", base_url="https://example.invalid")
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        usage=SimpleNamespace(prompt_tokens=120, completion_tokens=40),
    )
    client._client.chat.completions.create = MagicMock(return_value=completion)  # type: ignore[method-assign]

    with usage.track() as sink:
        client.complete_json(
            system="sys", user="usr", model="deepseek-chat", temperature=0.2, max_tokens=100
        )

    assert sink.prompt_tokens == 120
    assert sink.completion_tokens == 40
    assert sink.events[0].model == "deepseek-chat"
