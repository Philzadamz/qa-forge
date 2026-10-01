# 005 — `LLMClient.complete_json` must normalize provider SDK errors to `LLMError`

**Status:** accepted · **Date:** 2026-10-01

## Context
Report drafting (`app/routers/reports.py::draft_suite_report`) is designed to degrade
gracefully: if the AI call fails, it falls back to deterministic placeholder text instead of
failing the whole request, since a report is still useful half-drafted. It does this with
`except (LLMError, ValidationError)`.

In a live browser walkthrough of Phase 4 (not caught by the test suite, which only exercises
`FakeLLMClient`), clicking "Generate Report" against the real DeepSeek key — currently out of
balance — 500'd instead of degrading. `OpenAICompatibleClient.complete_json` and
`AnthropicClient.complete_json` only raised `LLMError` for the narrow "empty response from
model" case; every other failure (auth, rate limit, insufficient balance, timeout, network
error) propagated as the raw `openai`/`anthropic` SDK exception, which nothing upstream
catches. The one real failure mode this app has actually hit all session bypassed the fallback
it was built for.

## Decision
Both `complete_json` implementations now wrap their SDK call in
`try/except (openai.APIError | anthropic.APIError) as exc: raise LLMError(...) from exc`.
`LLMError` is the only exception type any caller needs to catch to handle "the AI call didn't
work, for any reason" — callers never need to know which SDK is in use or which of its
exception types can occur.

## Consequences
- Any future caller that wants AI-failure resilience (not just report drafting) can rely on
  `except LLMError` alone and it will actually fire for real-world failures, not just the
  empty-response edge case.
- `services/suites/generation_runner.py`'s job runner already caught `Exception` broadly for a
  different reason (recording `job.error` for any failure), so it was accidentally fine before
  this fix — but any other `except LLMError`-only call site would have had the same silent gap.
- Regression test: `tests/unit/test_ai_client.py` mocks a `402 Insufficient Balance` from the
  `openai` SDK and asserts it surfaces as `LLMError`.
