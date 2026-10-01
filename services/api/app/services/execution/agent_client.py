"""Tool-calling client for the execution agent (PRD §7.6, §8.4).

Separate from `app/services/ai/client.py`'s `LLMClient` (single JSON completion) because a
run is a multi-turn conversation where the model calls tools and gets their results back, not
one request/response — a different provider API surface (`tools=`/`tool_choice=` on
`chat.completions`, not `response_format=json_object`). Only DeepSeek (OpenAI-compatible
function calling) is implemented — the same scope decision as `ai/client.py`'s Anthropic path
(docs/decisions/004), but here Anthropic's tool-use message format differs enough from
OpenAI's that a stub would be untested, divergent code with no way to catch drift (exactly
the failure mode docs/decisions/005 fixed for the simpler case) — so it's a clear error
instead of a silent, never-exercised implementation.
"""

import json
from dataclasses import dataclass, field
from typing import Protocol

from app.core.config import Settings


class AgentClientError(RuntimeError):
    pass


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: dict[str, object]


@dataclass
class AgentReply:
    tool_calls: list[ToolCall] = field(default_factory=list)
    text: str = ""


class AgentClient(Protocol):
    def next_turn(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AgentReply: ...


class OpenAICompatibleAgentClient:
    """DeepSeek via the `openai` SDK's function-calling interface."""

    def __init__(self, *, api_key: str, base_url: str) -> None:
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def next_turn(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AgentReply:
        from openai import APIError

        try:
            response = self._client.chat.completions.create(  # type: ignore[call-overload]
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                messages=messages,
                tools=tools,
                tool_choice="auto",
            )
        except APIError as exc:
            raise AgentClientError(f"Agent LLM request failed: {exc}") from exc
        choice = response.choices[0].message
        calls = [
            ToolCall(
                id=tc.id,
                name=tc.function.name,
                arguments=json.loads(tc.function.arguments or "{}"),
            )
            for tc in (choice.tool_calls or [])
        ]
        return AgentReply(tool_calls=calls, text=choice.content or "")


class FakeAgentClient:
    """Test double (mirrors `FakeLLMClient`): returns one queued `AgentReply` per turn."""

    def __init__(self, turns: list[AgentReply]) -> None:
        self._turns = list(turns)
        self.calls: list[list[dict[str, object]]] = []

    def next_turn(
        self,
        *,
        messages: list[dict[str, object]],
        tools: list[dict[str, object]],
        model: str,
        temperature: float,
        max_tokens: int,
    ) -> AgentReply:
        self.calls.append(messages)
        if not self._turns:
            raise AgentClientError("FakeAgentClient ran out of queued turns")
        return self._turns.pop(0)


def build_agent_client(settings: Settings) -> AgentClient:
    if settings.ai_provider == "deepseek":
        if not settings.deepseek_api_key:
            raise AgentClientError("DEEPSEEK_API_KEY is not configured")
        return OpenAICompatibleAgentClient(
            api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url
        )
    if settings.ai_provider == "anthropic":
        raise AgentClientError("Agent mode against Anthropic isn't implemented yet")
    return FakeAgentClient(turns=[])
