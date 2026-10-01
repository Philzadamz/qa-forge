"""Script mode (PRD §7.6.1): after a passing agent run, freeze its action trace into a
deterministic script stored on the case (`TestCase.automation_script`); subsequent runs
replay it without calling the LLM, falling back to agent mode on failure ("self-heal").

Built from `CaseRunResult.raw_calls`, not from the audit-trail `CaseStepEvent.input_masked` —
`raw_calls` holds the model's tool calls exactly as emitted (a `fill` with a secret keeps
`secret_ref`, never the resolved plaintext), so the stored script can never leak a credential.
"""

import contextlib
from collections.abc import Callable
from dataclasses import dataclass

from app.core.enums import RunStepOutcome, TestStatus
from app.services.execution.agent import CaseRunResult, CaseStepEvent, dispatch_tool_call
from app.services.execution.agent_client import ToolCall
from app.services.execution.tools import BrowserTools, ToolError

# Tools that mutate/inspect the page in a way worth replaying; `snapshot` is agent-only
# (informational) and never needs replaying deterministically.
_REPLAYABLE_ACTIONS = {
    "navigate",
    "click",
    "fill",
    "select",
    "press",
    "wait_for",
    "assert_visible",
    "assert_url",
    "back",
    "go_idle",
}


def build_script(result: CaseRunResult) -> list[dict[str, object]] | None:
    """Returns a replayable script from a passing run, or None if the run didn't pass (PRD:
    "after a passing agent run")."""
    if result.status != TestStatus.PASSED:
        return None
    return [
        {"action": call.name, "arguments": call.arguments}
        for call in result.raw_calls
        if call.name in _REPLAYABLE_ACTIONS
    ]


@dataclass
class ScriptReplayResult:
    status: TestStatus
    actual_result: str
    steps: list[CaseStepEvent]


def replay_script(
    script: list[dict[str, object]],
    *,
    tools: BrowserTools,
    resolve_secret: Callable[[str], str],
) -> ScriptReplayResult:
    """Replays a stored script with no LLM call. Any step failing (an assertion returning
    false, a timeout, a missing element) ends the replay as Failed — callers should fall back
    to agent mode on this ("self-heal") per PRD §7.6.1, not treat it as a hard error."""
    import time

    events: list[CaseStepEvent] = []
    seq = 0
    for raw_step in script:
        seq += 1
        action = str(raw_step["action"])
        arguments_raw = raw_step.get("arguments", {})
        arguments: dict[str, object] = (
            dict(arguments_raw) if isinstance(arguments_raw, dict) else {}
        )
        call = ToolCall(id=f"replay-{seq}", name=action, arguments=arguments)
        started = time.monotonic()
        outcome = RunStepOutcome.PASS
        try:
            message = dispatch_tool_call(tools, call, resolve_secret)
        except ToolError as exc:
            outcome = RunStepOutcome.FAIL
            message = str(exc)
        except Exception as exc:
            outcome = RunStepOutcome.ERROR
            message = f"{type(exc).__name__}: {exc}"

        screenshot = None
        if outcome != RunStepOutcome.PASS or action in ("assert_visible", "assert_url"):
            with contextlib.suppress(Exception):
                screenshot = tools.screenshot()

        target = str(arguments.get("ref") or arguments.get("url") or arguments.get("pattern") or "")
        input_masked = (
            f"[SECRET:{arguments['secret_ref']}]" if arguments.get("secret_ref") else None
        )
        events.append(
            CaseStepEvent(
                seq=seq,
                action=action,
                target=target,
                input_masked=input_masked,
                assertion=action if action in ("assert_visible", "assert_url") else None,
                outcome=outcome,
                message=message,
                screenshot=screenshot,
                duration_ms=int((time.monotonic() - started) * 1000),
            )
        )

        if outcome != RunStepOutcome.PASS:
            return ScriptReplayResult(
                status=TestStatus.FAILED,
                actual_result=f"Script step {seq} ({action}) failed: {message}",
                steps=events,
            )
        if action in ("assert_visible", "assert_url") and message == "false":
            return ScriptReplayResult(
                status=TestStatus.FAILED,
                actual_result=f"Script assertion at step {seq} ({action}) did not hold.",
                steps=events,
            )

    final_screenshot = None
    with contextlib.suppress(Exception):
        final_screenshot = tools.screenshot()
    seq += 1
    events.append(
        CaseStepEvent(
            seq=seq,
            action="finish",
            target=None,
            input_masked=None,
            assertion=None,
            outcome=RunStepOutcome.PASS,
            message="Script replay completed without errors.",
            screenshot=final_screenshot,
            duration_ms=0,
        )
    )
    return ScriptReplayResult(
        status=TestStatus.PASSED,
        actual_result="Script replay completed without errors.",
        steps=events,
    )
