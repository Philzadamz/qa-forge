"""Token usage tracking (PRD §12 Observability "token usage"; Phase 8 usage dashboard).

A ContextVar sink rather than threading a return value through every LLM call site:
`call_structured`/`run_case_with_*_agent` are generic pipelines reused across five-plus
features, and changing their return shape would force every caller to unpack usage it mostly
doesn't care about. Instead, a job or request handler opens a sink with `track()` around the
AI-calling section, and the two OpenAI-compatible clients report into whatever sink is active
via `record()` — code that doesn't open a sink pays nothing and nothing breaks.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field

from app.core.metrics import AI_TOKENS


@dataclass
class UsageEvent:
    model: str
    prompt_tokens: int
    completion_tokens: int


@dataclass
class Sink:
    events: list[UsageEvent] = field(default_factory=list)

    @property
    def prompt_tokens(self) -> int:
        return sum(e.prompt_tokens for e in self.events)

    @property
    def completion_tokens(self) -> int:
        return sum(e.completion_tokens for e in self.events)


_current: ContextVar[Sink | None] = ContextVar("usage_sink", default=None)


@contextmanager
def track() -> Iterator[Sink]:
    sink = Sink()
    token = _current.set(sink)
    try:
        yield sink
    finally:
        _current.reset(token)


def record(*, model: str, prompt_tokens: int, completion_tokens: int) -> None:
    AI_TOKENS.labels(model=model, direction="prompt").inc(prompt_tokens)
    AI_TOKENS.labels(model=model, direction="completion").inc(completion_tokens)
    sink = _current.get()
    if sink is not None:
        sink.events.append(
            UsageEvent(
                model=model, prompt_tokens=prompt_tokens, completion_tokens=completion_tokens
            )
        )


def estimate_cost(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    cost_per_million_input: float,
    cost_per_million_output: float,
) -> float:
    return (prompt_tokens / 1_000_000) * cost_per_million_input + (
        completion_tokens / 1_000_000
    ) * cost_per_million_output
