from app.core.enums import TestStatus
from app.services.execution.agent import CaseRunResult
from app.services.execution.agent_client import ToolCall
from app.services.execution.script_mode import build_script, replay_script
from tests.unit.fake_browser_tools import FakeBrowserTools


def test_build_script_returns_none_for_non_passed_run() -> None:
    result = CaseRunResult(status=TestStatus.FAILED, actual_result="nope", confidence=0.1)
    assert build_script(result) is None


def test_build_script_excludes_snapshot_and_finish() -> None:
    result = CaseRunResult(
        status=TestStatus.PASSED,
        actual_result="ok",
        confidence=0.9,
        raw_calls=[
            ToolCall(id="1", name="navigate", arguments={"url": "http://x"}),
            ToolCall(id="2", name="snapshot", arguments={}),
            ToolCall(id="3", name="click", arguments={"ref": "#go"}),
            ToolCall(id="4", name="finish", arguments={"status": "Passed"}),
        ],
    )
    script = build_script(result)
    assert script == [
        {"action": "navigate", "arguments": {"url": "http://x"}},
        {"action": "click", "arguments": {"ref": "#go"}},
    ]


def test_build_script_keeps_secret_ref_never_plaintext() -> None:
    result = CaseRunResult(
        status=TestStatus.PASSED,
        actual_result="ok",
        confidence=0.9,
        raw_calls=[
            ToolCall(
                id="1", name="fill", arguments={"ref": "#password", "secret_ref": "demo_password"}
            ),
        ],
    )
    script = build_script(result)
    assert script is not None
    assert script[0]["arguments"] == {"ref": "#password", "secret_ref": "demo_password"}


def test_replay_script_success() -> None:
    script = [
        {"action": "navigate", "arguments": {"url": "http://x"}},
        {"action": "fill", "arguments": {"ref": "#u", "value": "demo"}},
        {"action": "click", "arguments": {"ref": "#go"}},
    ]
    tools = FakeBrowserTools()
    result = replay_script(script, tools=tools, resolve_secret=lambda name: "x")
    assert result.status == TestStatus.PASSED
    # the replay also takes a final screenshot after the last scripted step
    assert [c[0] for c in tools.calls] == ["navigate", "fill", "click", "screenshot"]


def test_replay_script_resolves_secret_ref_without_storing_plaintext() -> None:
    script = [{"action": "fill", "arguments": {"ref": "#password", "secret_ref": "demo_password"}}]
    tools = FakeBrowserTools()
    result = replay_script(script, tools=tools, resolve_secret=lambda name: "resolved-secret")
    assert tools.calls[0] == ("fill", {"ref": "#password", "value": "resolved-secret"})
    assert result.steps[0].input_masked == "[SECRET:demo_password]"
    assert "resolved-secret" not in str(result.steps[0].input_masked)


def test_replay_script_fails_on_tool_error() -> None:
    class FailingTools(FakeBrowserTools):
        def click(self, ref: str) -> str:
            from app.services.execution.tools import ToolError

            raise ToolError("nope")

    script = [{"action": "click", "arguments": {"ref": "#missing"}}]
    result = replay_script(script, tools=FailingTools(), resolve_secret=lambda name: "x")
    assert result.status == TestStatus.FAILED
    assert "nope" in result.actual_result


def test_replay_script_fails_on_false_assertion() -> None:
    tools = FakeBrowserTools(assert_visible_results={"#banner": False})
    script = [{"action": "assert_visible", "arguments": {"ref": "#banner"}}]
    result = replay_script(script, tools=tools, resolve_secret=lambda name: "x")
    assert result.status == TestStatus.FAILED
    assert "did not hold" in result.actual_result
