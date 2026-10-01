# 004 — DeepSeek now, Anthropic for production, via one provider-agnostic client

**Status:** accepted · **Date:** 2026-10-01

## Context
PRD §4.1 mandates the Anthropic Messages API as the AI provider. The user doesn't have an
Anthropic key yet and wants to build against DeepSeek in the meantime, switching to Anthropic
once a production key exists.

## Decision
The generation pipeline (`services/ai/{analyze,generate,orchestrator}.py`) talks only to an
`LLMClient` protocol (`services/ai/client.py`) — one method, `complete_json`. Three
implementations satisfy it:
- `OpenAICompatibleClient` — DeepSeek's chat API is OpenAI-compatible, so this is the `openai`
  SDK pointed at `settings.deepseek_base_url` with `response_format={"type": "json_object"}`.
  This is what's actually in use right now (`AI_PROVIDER=deepseek` in `.env`, once the user
  adds `DEEPSEEK_API_KEY`).
- `AnthropicClient` — the `anthropic` SDK, built to PRD §4.1's spec (tool-use-shaped JSON
  system prompt). Wired and importable, but unexercised — no key configured yet, so there's
  no live test for it. Switching to it in production is `AI_PROVIDER=anthropic` plus
  `ANTHROPIC_API_KEY` in `.env` — no pipeline code changes.
- `FakeLLMClient` — queued fixture responses, used by every automated test (PRD §13.3).
  `AI_PROVIDER` defaults to `fake` so a fresh checkout with no `.env` never tries a real call.

`build_llm_client(settings)` is the only place that branches on provider.

## Consequences
- Model names are config values (`ai_model_generation` etc. in `Settings`), never hard-coded,
  so today's `deepseek-chat` and tomorrow's Anthropic model name both flow through the same
  fields.
- The Anthropic path is genuinely untested against a live API — when the production key
  arrives, it needs at least a live smoke test (PRD's `-m live_llm` marker convention) before
  being trusted, the same way the DeepSeek path still does.
- Prompts were written provider-agnostically (system + user text, JSON-object response) rather
  than using Anthropic-specific tool-use blocks, so they work unmodified against either
  provider's JSON mode.
