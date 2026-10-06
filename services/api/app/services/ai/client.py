"""Provider-agnostic LLM client (PRD §8, ADM-AI-1).

The generation pipeline talks to `LLMClient.complete_json` only — it never imports the
`openai` or `anthropic` SDKs directly. Swapping providers (the user is on DeepSeek for now,
Anthropic once a production key exists — docs/decisions/004) is a `Settings.ai_provider`
change, not a pipeline rewrite. DeepSeek's chat API is OpenAI-compatible, so it's implemented
with the `openai` SDK pointed at DeepSeek's base URL rather than a bespoke HTTP client.
"""

from typing import Protocol

from app.core import usage
from app.core.config import Settings

LLM_TIMEOUT_SECONDS = 120.0


class LLMError(RuntimeError):
    pass


class LLMClient(Protocol):
    def complete_json(
        self, *, system: str, user: str, model: str, temperature: float, max_tokens: int
    ) -> str:
        """Returns raw JSON text. Callers validate it against a Pydantic schema."""
        ...


class OpenAICompatibleClient:
    """DeepSeek (and any other OpenAI-compatible provider) via the `openai` SDK."""

    def __init__(self, *, api_key: str, base_url: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(
            api_key=api_key, base_url=base_url, timeout=LLM_TIMEOUT_SECONDS, max_retries=1
        )

    def complete_json(
        self, *, system: str, user: str, model: str, temperature: float, max_tokens: int
    ) -> str:
        from openai import APIError

        try:
            response = self._client.chat.completions.create(
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            )
        except APIError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        if response.usage is not None:
            usage.record(
                model=model,
                prompt_tokens=response.usage.prompt_tokens,
                completion_tokens=response.usage.completion_tokens,
            )
        content = response.choices[0].message.content
        if not content:
            raise LLMError("Empty response from model")
        return content


class AnthropicClient:
    """Anthropic Messages API (PRD's mandated default, once a production key exists)."""

    def __init__(self, *, api_key: str) -> None:
        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)

    def complete_json(
        self, *, system: str, user: str, model: str, temperature: float, max_tokens: int
    ) -> str:
        import anthropic

        try:
            # The ignore below: this SDK's overloads pin `model` to a Literal of known model
            # names, which a config-driven `str` can never statically satisfy; unexercised
            # until a production Anthropic key exists (docs/decisions/004).
            response = self._client.messages.create(  # type: ignore[call-overload]
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=f"{system}\n\nRespond with a single JSON object and nothing else.",
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.APIError as exc:
            raise LLMError(f"LLM request failed: {exc}") from exc
        usage.record(
            model=model,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        )
        parts = [block.text for block in response.content if block.type == "text"]
        if not parts:
            raise LLMError("Empty response from model")
        return "".join(parts)


class FakeLLMClient:
    """Test double (PRD §13.3): returns queued fixture responses instead of calling out.

    Each call pops the next response from `responses`. Pass one JSON string per expected
    call, in order. Records every call's (system, user) for assertions.
    """

    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, str]] = []

    def complete_json(
        self, *, system: str, user: str, model: str, temperature: float, max_tokens: int
    ) -> str:
        self.calls.append({"system": system, "user": user, "model": model})
        if not self._responses:
            raise LLMError("FakeLLMClient ran out of queued responses")
        return self._responses.pop(0)


def build_llm_client(settings: Settings) -> LLMClient:
    if settings.ai_provider == "deepseek":
        if not settings.deepseek_api_key:
            raise LLMError("DEEPSEEK_API_KEY is not configured")
        return OpenAICompatibleClient(
            api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url
        )
    if settings.ai_provider == "openai_compatible":
        if not settings.openai_compatible_api_key or not settings.openai_compatible_base_url:
            raise LLMError("OPENAI_COMPATIBLE_API_KEY and OPENAI_COMPATIBLE_BASE_URL are required")
        return OpenAICompatibleClient(
            api_key=settings.openai_compatible_api_key,
            base_url=settings.openai_compatible_base_url,
        )
    if settings.ai_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is not configured")
        return AnthropicClient(api_key=settings.anthropic_api_key)
    return FakeLLMClient(responses=[])
