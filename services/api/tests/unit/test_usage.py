from app.core import usage


def test_record_outside_a_sink_is_a_noop() -> None:
    usage.record(model="m", prompt_tokens=10, completion_tokens=5)  # no active sink; must not raise


def test_track_collects_events_from_record() -> None:
    with usage.track() as sink:
        usage.record(model="deepseek-chat", prompt_tokens=100, completion_tokens=20)
        usage.record(model="deepseek-chat", prompt_tokens=50, completion_tokens=10)

    assert sink.prompt_tokens == 150
    assert sink.completion_tokens == 30
    assert len(sink.events) == 2


def test_nested_sinks_only_collect_their_own_scope() -> None:
    with usage.track() as outer:
        usage.record(model="m", prompt_tokens=1, completion_tokens=1)
        with usage.track() as inner:
            usage.record(model="m", prompt_tokens=2, completion_tokens=2)
        usage.record(model="m", prompt_tokens=3, completion_tokens=3)

    assert inner.prompt_tokens == 2
    assert outer.prompt_tokens == 4


def test_record_after_track_exits_is_a_noop() -> None:
    with usage.track() as sink:
        pass
    usage.record(model="m", prompt_tokens=99, completion_tokens=99)
    assert sink.events == []


def test_estimate_cost() -> None:
    cost = usage.estimate_cost(
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        cost_per_million_input=0.5,
        cost_per_million_output=1.5,
    )
    assert cost == 2.0


def test_estimate_cost_is_zero_with_default_rates() -> None:
    assert (
        usage.estimate_cost(
            prompt_tokens=1_000_000,
            completion_tokens=1_000_000,
            cost_per_million_input=0.0,
            cost_per_million_output=0.0,
        )
        == 0.0
    )


def test_agent_client_reports_token_usage_to_the_active_sink() -> None:
    from types import SimpleNamespace
    from unittest.mock import MagicMock

    from app.services.execution.agent_client import OpenAICompatibleAgentClient

    client = OpenAICompatibleAgentClient(api_key="k", base_url="https://example.invalid")
    completion = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="done", tool_calls=None))],
        usage=SimpleNamespace(prompt_tokens=300, completion_tokens=75),
    )
    client._client.chat.completions.create = MagicMock(return_value=completion)  # type: ignore[method-assign]

    with usage.track() as sink:
        client.next_turn(
            messages=[], tools=[], model="deepseek-chat", temperature=0.0, max_tokens=50
        )

    assert (sink.prompt_tokens, sink.completion_tokens) == (300, 75)
