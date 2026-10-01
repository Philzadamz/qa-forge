import pytest
from pydantic import BaseModel

from app.services.ai.client import FakeLLMClient, LLMError
from app.services.ai.structured import call_structured


class Thing(BaseModel):
    name: str
    count: int


def test_valid_json_on_first_try() -> None:
    client = FakeLLMClient(responses=['{"name": "widget", "count": 3}'])
    result = call_structured(client, system="sys", user="usr", schema=Thing, model="m")
    assert result == Thing(name="widget", count=3)
    assert len(client.calls) == 1


def test_strips_markdown_code_fences() -> None:
    client = FakeLLMClient(responses=['```json\n{"name": "widget", "count": 3}\n```'])
    result = call_structured(client, system="sys", user="usr", schema=Thing, model="m")
    assert result == Thing(name="widget", count=3)


def test_repairs_invalid_json_on_retry() -> None:
    client = FakeLLMClient(
        responses=[
            '{"name": "widget", "count": "not a number"}',
            '{"name": "widget", "count": 3}',
        ]
    )
    result = call_structured(client, system="sys", user="usr", schema=Thing, model="m")
    assert result == Thing(name="widget", count=3)
    assert len(client.calls) == 2
    assert "Validation errors" in client.calls[1]["user"]


def test_raises_after_repair_also_fails() -> None:
    client = FakeLLMClient(responses=["not json at all", "still not json"])
    with pytest.raises(LLMError, match="did not match Thing"):
        call_structured(client, system="sys", user="usr", schema=Thing, model="m")


def test_fake_llm_raises_when_exhausted() -> None:
    client = FakeLLMClient(responses=[])
    with pytest.raises(LLMError, match="ran out of queued responses"):
        call_structured(client, system="sys", user="usr", schema=Thing, model="m")
