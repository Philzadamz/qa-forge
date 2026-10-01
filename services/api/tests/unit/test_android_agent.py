from app.core.enums import RunStepOutcome, TestStatus
from app.services.execution.agent_client import AgentReply, FakeAgentClient, ToolCall
from app.services.execution.android_agent import run_case_with_android_agent
from tests.unit.fake_android_tools import FakeAndroidTools


def _finish_call(status: str, actual_result: str, confidence: float = 0.9) -> ToolCall:
    return ToolCall(
        id="call-finish",
        name="finish",
        arguments={"status": status, "actual_result": actual_result, "confidence": confidence},
    )


def test_single_tap_then_finish_passed() -> None:
    client = FakeAgentClient(
        turns=[
            AgentReply(tool_calls=[ToolCall(id="c1", name="tap", arguments={"ref": "e3"})]),
            AgentReply(tool_calls=[_finish_call("Passed", "It worked.")]),
        ]
    )
    tools = FakeAndroidTools()
    result = run_case_with_android_agent(
        client,
        tools=tools,
        feature="Login",
        scenario="Check login",
        steps=["Tap login"],
        expected_result="Logs in",
        app_label="Demo App",
        resolve_secret=lambda name: "unused",
        model="m",
    )
    assert result.status == TestStatus.PASSED
    assert result.actual_result == "It worked."
    assert [c.name for c in result.raw_calls] == ["tap"]
    assert [s.action for s in result.steps] == ["tap", "finish"]
    assert result.steps[-1].screenshot is not None


def test_type_with_secret_ref_never_exposes_plaintext() -> None:
    client = FakeAgentClient(
        turns=[
            AgentReply(
                tool_calls=[
                    ToolCall(
                        id="c1", name="type", arguments={"ref": "e5", "secret_ref": "demo_password"}
                    )
                ]
            ),
            AgentReply(tool_calls=[_finish_call("Passed", "ok")]),
        ]
    )
    tools = FakeAndroidTools()
    result = run_case_with_android_agent(
        client,
        tools=tools,
        feature="f",
        scenario="s",
        steps=[],
        expected_result="e",
        app_label="Demo App",
        resolve_secret=lambda name: "the-real-password-value",
        model="m",
    )
    type_step = result.steps[0]
    assert type_step.input_masked == "[SECRET:demo_password]"
    assert "the-real-password-value" not in (type_step.message or "")
    assert tools.calls[0] == ("type", {"ref": "e5", "value": "the-real-password-value"})
    assert result.raw_calls[0].arguments == {"ref": "e5", "secret_ref": "demo_password"}


def test_tool_error_marks_step_failed_and_continues() -> None:
    client = FakeAgentClient(
        turns=[
            AgentReply(
                tool_calls=[ToolCall(id="c1", name="scroll_to", arguments={"text": "Missing"})]
            ),
            AgentReply(tool_calls=[_finish_call("Failed", "Could not find it.")]),
        ]
    )
    tools = FakeAndroidTools(wait_for_fails={"Missing"})
    result = run_case_with_android_agent(
        client,
        tools=tools,
        feature="f",
        scenario="s",
        steps=[],
        expected_result="e",
        app_label="Demo App",
        resolve_secret=lambda name: "x",
        model="m",
    )
    assert result.steps[0].outcome == RunStepOutcome.FAIL
    assert result.status == TestStatus.FAILED


def test_max_steps_exceeded_without_finish() -> None:
    client = FakeAgentClient(
        turns=[
            AgentReply(tool_calls=[ToolCall(id=f"c{i}", name="snapshot", arguments={})])
            for i in range(3)
        ]
    )
    result = run_case_with_android_agent(
        client,
        tools=FakeAndroidTools(),
        feature="f",
        scenario="s",
        steps=[],
        expected_result="e",
        app_label="Demo App",
        resolve_secret=lambda name: "x",
        model="m",
        max_steps=3,
    )
    assert result.status == TestStatus.BLOCKED
    assert result.steps[-1].action == "max_steps_exceeded"


def test_on_step_callback_receives_every_event() -> None:
    client = FakeAgentClient(
        turns=[
            AgentReply(tool_calls=[ToolCall(id="c1", name="snapshot", arguments={})]),
            AgentReply(tool_calls=[_finish_call("Passed", "ok")]),
        ]
    )
    seen = []
    run_case_with_android_agent(
        client,
        tools=FakeAndroidTools(),
        feature="f",
        scenario="s",
        steps=[],
        expected_result="e",
        app_label="Demo App",
        resolve_secret=lambda name: "x",
        model="m",
        on_step=seen.append,
    )
    assert [e.action for e in seen] == ["snapshot", "finish"]
