"""Execution agent loop: drives one test case through `BrowserTools` via tool-calling
(PRD §7.6.1 agent mode, §8.4).

Decoupled from persistence on purpose (mirrors `ai/orchestrator.py`'s split from
`suites/generation_runner.py`): this module knows nothing about the DB or SSE — it calls
`on_step` once per tool invocation and returns a final `CaseRunResult`. The caller
(`execution_runner.py`) turns each `CaseStepEvent` into a `RunStep` row + `Evidence` row and
publishes it over SSE, so the live run view updates in real time as the agent works, not only
once the whole case finishes.
"""

import contextlib
from collections.abc import Callable
from dataclasses import dataclass, field

from app.core.enums import RunStepOutcome, TestStatus
from app.services.ai.masking import mask_text
from app.services.execution.agent_client import AgentClient, AgentClientError, ToolCall
from app.services.execution.tools import BrowserTools, ToolError

SYSTEM_PROMPT = """You are a careful, methodical QA tester operating a web browser through a \
constrained set of tools. Rules:
- Only interact with the allowlisted target host given in the task. Never navigate elsewhere.
- Never guess or invent credentials. If a field needs a secret, use `secret_ref` with the \
exact name given in the task — never type a credential value directly.
- Call `snapshot()` after any navigation or significant page change before deciding your next \
action, so you act on the current state of the page, not a stale one.
- Take a screenshot (the runner does this automatically around assertions and at the end) and \
decide pass/fail strictly by comparing what you observed against the case's Expected Result — \
do not mark something Passed on a guess.
- If the expected result genuinely cannot be verified (e.g. a blocking error unrelated to the \
scenario under test), call finish with status "Blocked" and explain why.
- You must end every run by calling `finish`. Confidence is a 0-1 number: how sure you are of \
the status given what you observed.
- Stop and call finish once you've gathered enough evidence — don't take unnecessary actions."""

TOOL_SCHEMAS: list[dict[str, object]] = [
    {
        "type": "function",
        "function": {
            "name": "navigate",
            "description": "Go to a URL. Must be within the allowlisted target.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "snapshot",
            "description": (
                "Get the current page's visible interactive elements (with refs) and text."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "click",
            "description": "Click an element by its snapshot ref.",
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
            "name": "fill",
            "description": (
                "Type a value into an input by its snapshot ref. Provide exactly one of "
                "`value` (literal text) or `secret_ref` (the exact name of a configured "
                "secret, resolved server-side — never ask for or type a secret's value)."
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
            "name": "select",
            "description": "Choose an option in a <select> by its snapshot ref.",
            "parameters": {
                "type": "object",
                "properties": {"ref": {"type": "string"}, "option": {"type": "string"}},
                "required": ["ref", "option"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "press",
            "description": "Press a keyboard key (e.g. 'Enter', 'Escape', 'Tab').",
            "parameters": {
                "type": "object",
                "properties": {"key": {"type": "string"}},
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "wait_for",
            "description": "Wait for text or a ref to appear, up to a timeout.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {"type": "string"},
                    "ref": {"type": "string"},
                    "timeout_ms": {"type": "integer"},
                },
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assert_visible",
            "description": "Check that text or a ref is currently visible. Returns true/false.",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}, "ref": {"type": "string"}},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "assert_url",
            "description": "Check the current URL matches a regex pattern. Returns true/false.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "back",
            "description": "Go back to the previous page in browser history.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "go_idle",
            "description": (
                "Wait, to simulate session-timeout scenarios. Capped well below the literal "
                "minutes given — configure a short session timeout on the target for precise "
                "timeout testing rather than relying on this for exact timing."
            ),
            "parameters": {
                "type": "object",
                "properties": {"minutes": {"type": "number"}},
                "required": ["minutes"],
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


@dataclass
class CaseStepEvent:
    seq: int
    action: str
    target: str | None
    input_masked: str | None
    assertion: str | None
    outcome: RunStepOutcome
    message: str
    screenshot: bytes | None
    duration_ms: int


@dataclass
class CaseRunResult:
    status: TestStatus
    actual_result: str
    confidence: float
    steps: list[CaseStepEvent] = field(default_factory=list)
    # The model's own tool calls, verbatim (never a resolved secret value — `fill` keeps
    # `secret_ref`, not the plaintext `value`) — script_mode.py builds a replayable script
    # from this, not from `steps` (whose `input_masked` is lossy by design).
    raw_calls: list[ToolCall] = field(default_factory=list)


SecretResolver = Callable[[str], str]


def _case_prompt(
    *, feature: str, scenario: str, steps: list[str], expected_result: str, target_url: str
) -> str:
    step_lines = "\n".join(f"{i + 1}. {s}" for i, s in enumerate(steps)) or "(none given)"
    return f"""Target: {target_url}
Feature: {feature}

Scenario: {scenario}

Suggested steps:
{step_lines}

Expected Result: {expected_result}

Carry out this scenario against the target and call finish() with your verdict."""


_ASSERTION_ACTIONS = {"assert_visible", "assert_url"}
_SENSITIVE_ARG_KEYS = {"ref", "option", "key", "pattern", "timeout_ms", "minutes", "text"}


def _describe_call(call: ToolCall) -> tuple[str | None, str | None, str | None]:
    """Returns (target, input_masked, assertion) for a RunStep row."""
    args = call.arguments
    if call.name in ("click", "fill", "select", "wait_for", "assert_visible"):
        target = str(args.get("ref") or args.get("text") or "")
    elif call.name == "navigate":
        target = str(args.get("url", ""))
    elif call.name == "assert_url":
        target = str(args.get("pattern", ""))
    else:
        target = None

    input_masked = None
    if call.name == "fill":
        if args.get("secret_ref"):
            input_masked = f"[SECRET:{args['secret_ref']}]"
        elif args.get("value") is not None:
            input_masked = mask_text(str(args["value"])).text

    assertion = None
    if call.name in _ASSERTION_ACTIONS:
        assertion = str(args.get("text") or args.get("pattern") or args.get("ref") or "")

    return target, input_masked, assertion


def run_case_with_agent(
    client: AgentClient,
    *,
    tools: BrowserTools,
    feature: str,
    scenario: str,
    steps: list[str],
    expected_result: str,
    target_url: str,
    resolve_secret: SecretResolver,
    model: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    max_steps: int = 20,
    on_step: "Callable[[CaseStepEvent], None] | None" = None,
) -> CaseRunResult:
    import time

    messages: list[dict[str, object]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": _case_prompt(
                feature=feature,
                scenario=scenario,
                steps=steps,
                expected_result=expected_result,
                target_url=target_url,
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
                        "function": {"name": call.name, "arguments": _dump_args(call.arguments)},
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
                with contextlib.suppress(Exception):  # page may already be gone
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
    with contextlib.suppress(Exception):  # page may already be gone; don't fail the step over this
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


def _dump_args(arguments: dict[str, object]) -> str:
    import json

    return json.dumps(arguments)


def dispatch_tool_call(tools: BrowserTools, call: ToolCall, resolve_secret: SecretResolver) -> str:
    args = call.arguments
    if call.name == "navigate":
        return tools.navigate(str(args["url"]))
    if call.name == "snapshot":
        import json

        return json.dumps(tools.snapshot())
    if call.name == "click":
        return tools.click(str(args["ref"]))
    if call.name == "fill":
        value = args.get("value")
        secret_ref = args.get("secret_ref")
        if secret_ref and value:
            raise ToolError("fill: give only one of value or secret_ref, not both")
        if secret_ref:
            value = resolve_secret(str(secret_ref))
        if value is None:
            raise ToolError("fill: give either value or secret_ref")
        return tools.fill(str(args["ref"]), str(value))
    if call.name == "select":
        return tools.select(str(args["ref"]), str(args["option"]))
    if call.name == "press":
        return tools.press(str(args["key"]))
    if call.name == "wait_for":
        timeout = args.get("timeout_ms")
        return tools.wait_for(
            text=_opt_str(args.get("text")),
            ref=_opt_str(args.get("ref")),
            timeout_ms=int(str(timeout)) if timeout else 5000,
        )
    if call.name == "assert_visible":
        visible = tools.assert_visible(
            text=_opt_str(args.get("text")), ref=_opt_str(args.get("ref"))
        )
        return "true" if visible else "false"
    if call.name == "assert_url":
        matched = tools.assert_url(str(args["pattern"]))
        return "true" if matched else "false"
    if call.name == "back":
        return tools.back()
    if call.name == "go_idle":
        return tools.go_idle(float(str(args.get("minutes", 1))))
    raise ToolError(f"Unknown tool: {call.name}")


def _opt_str(value: object) -> str | None:
    return str(value) if value else None
