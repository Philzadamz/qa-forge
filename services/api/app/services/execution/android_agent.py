"""Execution agent loop for Android (PRD §7.6.3 agent mode, §8.4) — drives one test case
through `AndroidTools` via tool-calling.

Deliberately a separate module from `agent.py` rather than a shared generic engine: the two
tool sets differ enough in their arguments (`tap(ref)` vs `click(ref)`, `type(ref,
value|secret_ref)` vs `fill(ref, value|secret_ref)`, `swipe(dir)`/`scroll_to(text)` with no Web
equivalent) that a shared loop would need as much per-target parameterization as it would save
in duplicated control flow — and this keeps Phase 5's already-verified Web loop untouched
rather than risking a regression in it for Phase 7's sake. `CaseStepEvent`/`CaseRunResult` are
genuinely generic (no Web-specific fields) and are reused as-is from `agent.py`.
"""

import contextlib
import json
import time
from collections.abc import Callable

from app.core.enums import RunStepOutcome, TestStatus
from app.services.ai.masking import mask_text
from app.services.execution.agent import CaseRunResult, CaseStepEvent, SecretResolver
from app.services.execution.agent_client import AgentClient, AgentClientError, ToolCall
from app.services.execution.android_tools import AndroidTools, ToolError

SYSTEM_PROMPT = """You are a careful, methodical QA tester operating an Android app through a \
constrained set of tools. Rules:
- Only interact with the app under test. Never assume another app's UI is relevant.
- Never guess or invent credentials. If a field needs a secret, use `secret_ref` with the \
exact name given in the task — never type a credential value directly.
- Call `snapshot()` after any navigation or significant screen change before deciding your \
next action, so you act on the current state of the screen, not a stale one.
- Decide pass/fail strictly by comparing what you observed against the case's Expected Result \
— do not mark something Passed on a guess.
- If the expected result genuinely cannot be verified (e.g. a blocking error unrelated to the \
scenario under test), call finish with status "Blocked" and explain why.
- You must end every run by calling `finish`. Confidence is a 0-1 number: how sure you are of \
the status given what you observed.
- Stop and call finish once you've gathered enough evidence — don't take unnecessary actions."""

TOOL_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "snapshot",
            "description": "Get the current screen's interactive elements (with refs) and text.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "tap",
            "description": "Tap an element by its snapshot ref.",
            "parameters": {
                "type": "object",
                "properties": {"ref": {"type": "string"}},
                "required": ["ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "type",
            "description": (
                "Type a value into a focused/editable element by its snapshot ref. Provide "
                "exactly one of `value` (literal text) or `secret_ref` (the exact name of a "
                "configured secret, resolved server-side — never ask for or type a secret's "
                "value)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "ref": {"type": "string"},
                    "value": {"type": "string"},
                    "secret_ref": {"type": "string"},
                },
                "required": ["ref"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "swipe",
            "description": "Swipe the screen in a direction.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {"type": "string", "enum": ["up", "down", "left", "right"]}
                },
                "required": ["direction"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "scroll_to",
            "description": "Scroll (swiping up repeatedly) until the given text is visible.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "back",
            "description": "Press the Android back button.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "home",
            "description": "Press the Android home button.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "launch_app",
            "description": "(Re)launch the app under test.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "background_app",
            "description": (
                "Send the app to the background for a number of seconds, to simulate "
                "session timeout."
            ),
            "parameters": {
                "type": "object",
                "properties": {"seconds": {"type": "number"}},
                "required": ["seconds"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "rotate",
            "description": "Rotate the device.",
            "parameters": {
                "type": "object",
                "properties": {
                    "orientation": {"type": "string", "enum": ["portrait", "landscape"]}
                },
                "required": ["orientation"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for",
            "description": "Wait for text to appear, up to a timeout.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "timeout_ms": {"type": "integer"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assert_visible",
            "description": "Check that text is currently visible on screen. Returns true/false.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Conclude the case with a final status, actual result, and confidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["Passed", "Failed", "Blocked"]},
                    "actual_result": {"type": "string"},
                    "confidence": {"type": "number"},
                },
                "required": ["status", "actual_result", "confidence"],
            },
        },
    },
]


def _case_prompt(
    *, feature: str, scenario: str, steps: list[str], expected_result: str, app_label: str
) -> str:
    step_lines = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps)) or "(none given)"
    return f"""App under test: {app_label}
Feature: {feature}

Scenario: {scenario}

Suggested steps:
{step_lines}

Expected Result: {expected_result}

Carry out this scenario in the app and call finish() with your verdict."""


_ASSERTION_ACTIONS = {"assert_visible"}


def _describe_call(call: ToolCall) -> tuple[str | None, str | None, str | None]:
    args = call.arguments
    if call.name in ("tap", "type"):
        target = str(args.get("ref", ""))
    elif call.name in ("swipe", "rotate"):
        target = str(args.get("direction") or args.get("orientation") or "")
    elif call.name in ("scroll_to", "wait_for", "assert_visible"):
        target = str(args.get("text", ""))
    else:
        target = None

    input_masked = None
    if call.name == "type":
        if args.get("secret_ref"):
            input_masked = f"[SECRET:{args['secret_ref']}]"
        elif args.get("value") is not None:
            input_masked = mask_text(str(args["value"])).text

    assertion = str(args.get("text", "")) if call.name == "assert_visible" else None
    return target, input_masked, assertion


def dispatch_tool_call(tools: AndroidTools, call: ToolCall, resolve_secret: SecretResolver) -> str:
    args = call.arguments
    if call.name == "snapshot":
        return json.dumps(tools.snapshot())
    if call.name == "tap":
        return tools.tap(str(args["ref"]))
    if call.name == "type":
        value = args.get("value")
        secret_ref = args.get("secret_ref")
        if secret_ref and value:
            raise ToolError("type: give only one of value or secret_ref, not both")
        if secret_ref:
            value = resolve_secret(str(secret_ref))
        if value is None:
            raise ToolError("type: give either value or secret_ref")
        return tools.type(str(args["ref"]), str(value))
    if call.name == "swipe":
        return tools.swipe(str(args["direction"]))
    if call.name == "scroll_to":
        return tools.scroll_to(str(args["text"]))
    if call.name == "back":
        return tools.back()
    if call.name == "home":
        return tools.home()
    if call.name == "launch_app":
        return tools.launch_app()
    if call.name == "background_app":
        return tools.background_app(float(str(args.get("seconds", 1))))
    if call.name == "rotate":
        return tools.rotate(str(args["orientation"]))
    if call.name == "wait_for":
        timeout = args.get("timeout_ms")
        return tools.wait_for(str(args["text"]), timeout_ms=int(str(timeout)) if timeout else 5000)
    if call.name == "assert_visible":
        return "true" if tools.assert_visible(str(args["text"])) else "false"
    raise ToolError(f"Unknown tool: {call.name}")


def run_case_with_android_agent(
    client: AgentClient,
    *,
    tools: AndroidTools,
    feature: str,
    scenario: str,
    steps: list[str],
    expected_result: str,
    app_label: str,
    resolve_secret: SecretResolver,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    max_steps: int = 20,
    on_step: "Callable[[CaseStepEvent], None] | None" = None,
) -> CaseRunResult:
    messages: list[dict[str, object]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _case_prompt(
                feature=feature,
                scenario=scenario,
                steps=steps,
                expected_result=expected_result,
                app_label=app_label,
            ),
        },
    ]
    events: list[CaseStepEvent] = []
    raw_calls: list[ToolCall] = []
    seq = 0

    def emit(event: CaseStepEvent) -> None:
        events.append(event)
        if on_step is not None:
            on_step(event)

    for _ in range(max_steps):
        try:
            reply = client.next_turn(
                messages=messages,
                tools=TOOL_SCHEMAS,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except AgentClientError as exc:
            seq += 1
            emit(
                CaseStepEvent(
                    seq=seq,
                    action="agent_error",
                    target=None,
                    input_masked=None,
                    assertion=None,
                    outcome=RunStepOutcome.ERROR,
                    message=str(exc),
                    screenshot=None,
                    duration_ms=0,
                )
            )
            return CaseRunResult(
                status=TestStatus.BLOCKED,
                actual_result=f"Agent error: {exc}",
                confidence=0.0,
                steps=events,
                raw_calls=raw_calls,
            )

        if not reply.tool_calls:
            messages.append({"role": "assistant", "content": reply.text or ""})
            messages.append(
                {
                    "role": "user",
                    "content": "Call one of the provided tools; call finish() when done.",
                }
            )
            continue

        messages.append(
            {
                "role": "assistant",
                "content": reply.text or None,
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {"name": call.name, "arguments": json.dumps(call.arguments)},
                    }
                    for call in reply.tool_calls
                ],
            }
        )

        for call in reply.tool_calls:
            seq += 1
            target, input_masked, assertion = _describe_call(call)
            started = time.monotonic()

            if call.name == "finish":
                status = TestStatus(str(call.arguments.get("status", "Blocked")))
                actual_result = str(call.arguments.get("actual_result", ""))
                confidence = float(str(call.arguments.get("confidence", 0.0)))
                screenshot: bytes | None = tools.screenshot()
                emit(
                    CaseStepEvent(
                        seq=seq,
                        action="finish",
                        target=None,
                        input_masked=None,
                        assertion=None,
                        outcome=RunStepOutcome.PASS
                        if status == TestStatus.PASSED
                        else RunStepOutcome.FAIL
                        if status == TestStatus.FAILED
                        else RunStepOutcome.SKIP,
                        message=actual_result,
                        screenshot=screenshot,
                        duration_ms=int((time.monotonic() - started) * 1000),
                    )
                )
                return CaseRunResult(
                    status=status,
                    actual_result=actual_result,
                    confidence=confidence,
                    steps=events,
                    raw_calls=raw_calls,
                )

            raw_calls.append(call)
            outcome = RunStepOutcome.PASS
            message = ""
            try:
                message = dispatch_tool_call(tools, call, resolve_secret)
            except ToolError as exc:
                outcome = RunStepOutcome.FAIL
                message = str(exc)
            except Exception as exc:
                outcome = RunStepOutcome.ERROR
                message = f"{type(exc).__name__}: {exc}"

            screenshot = None
            if call.name in _ASSERTION_ACTIONS or outcome != RunStepOutcome.PASS:
                with contextlib.suppress(Exception):  # session may already be gone
                    screenshot = tools.screenshot()

            emit(
                CaseStepEvent(
                    seq=seq,
                    action=call.name,
                    target=target,
                    input_masked=input_masked,
                    assertion=assertion,
                    outcome=outcome,
                    message=message,
                    screenshot=screenshot,
                    duration_ms=int((time.monotonic() - started) * 1000),
                )
            )
            messages.append({"role": "tool", "tool_call_id": call.id, "content": message})

    screenshot = None
    with contextlib.suppress(Exception):
        screenshot = tools.screenshot()
    seq += 1
    emit(
        CaseStepEvent(
            seq=seq,
            action="max_steps_exceeded",
            target=None,
            input_masked=None,
            assertion=None,
            outcome=RunStepOutcome.ERROR,
            message="Reached the step limit without calling finish().",
            screenshot=screenshot,
            duration_ms=0,
        )
    )
    return CaseRunResult(
        status=TestStatus.BLOCKED,
        actual_result="Agent did not conclude within the step limit.",
        confidence=0.0,
        steps=events,
        raw_calls=raw_calls,
    )
