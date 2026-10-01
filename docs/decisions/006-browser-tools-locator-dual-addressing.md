# 006 — `BrowserTools` locators accept both snapshot refs and raw CSS selectors

**Status:** accepted · **Date:** 2026-10-01

## Context
Agent-mode tool calls (`click`, `fill`, `wait_for`, …) address elements by a `ref` the model
got from a prior `snapshot()` call — a short id (`e1`, `e2`, …) the snapshot JS assigns via a
`data-qa-ref` DOM attribute. Deterministic default routines (`deterministic.py`) never call
`snapshot()` — they're hand-written against `infra/demo-target`'s known markup and address
elements with real CSS selectors (`#username`, `button[type=submit]`) directly.

`BrowserTools._locator` originally only understood the `data-qa-ref` form, always wrapping its
argument as `[data-qa-ref="{ref}"]`. This was never exercised against a real page until the
Phase 5 live integration tests (`tests/execution/`, Playwright + a real demo-target server) —
every deterministic routine timed out, because `#username` became the literal (nonsensical)
selector `[data-qa-ref="#username"]`.

## Decision
`_locator` tells the two addressing styles apart by shape: a snapshot ref always matches
`^e\d+$` (the JS snapshot's own naming scheme) and is wrapped as `[data-qa-ref="..."]`;
anything else is passed to `page.locator()` unchanged, i.e. treated as a real CSS selector.
One method serves both callers — the agent loop and the deterministic routines — without
either needing to know which addressing style the other uses.

## Consequences
- Fake-tools unit tests (`tests/unit/fake_browser_tools.py`) can't catch this class of bug —
  they don't model real selector resolution at all. The live tests in `tests/execution/`
  (real Chromium + real demo-target) are what actually exercise `_locator`'s selector
  handling; losing that suite (e.g. if Playwright browsers aren't installed in some
  environment) means losing the only thing that would catch a regression here. Both live test
  files skip cleanly via `pytest.skip` if Chromium isn't installed, rather than failing, so
  CI without browser binaries degrades gracefully instead of blocking — but that also means a
  `_locator` regression would go unnoticed wherever that skip fires.
- Deterministic routines stay simple, ordinary Playwright-selector code — they don't need to
  know about the snapshot-ref scheme at all.
- If a snapshot-ref pattern (`eN`) ever collided with a legitimate hand-written CSS selector,
  this would misresolve. Not a concern today (no routine uses a bare `eN`-shaped selector),
  but worth remembering if that ever changes.
