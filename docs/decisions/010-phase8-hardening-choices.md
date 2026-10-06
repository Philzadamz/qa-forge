# 010 — Phase 8 hardening: usage tracking, retention, CSRF, scanning, and open items

**Status:** accepted · **Date:** 2026-10-04

## Context
Phase 8 closes the PRD §12 checklist: token usage, a usage dashboard, a readable audit log,
retention, metrics, and dependency scanning. Several of these touch code paths that were already
verified in earlier phases, so the choices below favor small, contained changes over refactors.

## Decisions

1. **Token usage is captured with a ContextVar sink, not a return-value change.**
   `LLMClient.complete_json` and `AgentClient.next_turn` report usage into whatever sink is active
   (`app/core/usage.py`). Job and request entry points open the sink around their AI-calling
   section and persist a `usage_records` row. Changing the return type would have forced edits
   across six structured-generation call sites and the execution agent loops, all of which are
   covered by passing tests today.

2. **Cost is computed from configured rates, defaulting to $0.** `AI_COST_PER_MILLION_*` are
   operator-set. A hardcoded price would go stale as providers change rates and would present a
   guess as a fact. The dashboard states this next to the cost figure.

3. **Retention runs as a CLI command, not an in-process scheduler.** `python -m app.cli
   retention-sweep` (or `make retention-sweep`) is meant for cron. Local mode has no worker
   process (docs/decisions/001), and an in-process timer would fire on every API worker.
   Defaults: evidence and uploaded/rendered files 180 days, audit log 730 days. Story and report
   rows keep their text; only the raw file is reclaimed. Evidence rows are deleted, and
   `RunStep.screenshot_evidence_id` is nulled first because the foreign key has no `ON DELETE`.

4. **Deleting a project purges its storage objects immediately.** The row is still soft-deleted
   (recoverable by an operator), but evidence, story uploads, reports, and APKs are removed from
   storage at the moment of deletion, as PRD §12 requires. Shared admin templates are excluded.

5. **CSRF is covered by `SameSite=Lax` plus JSON-only mutation, not a token.** Auth cookies are
   `httpOnly` and `SameSite=Lax`, so browsers don't attach them to cross-site POSTs. A grep of the
   routers confirms no GET handler writes state, which is the other half of that argument. A
   synchronizer token would add a second mechanism to keep in step with the frontend. Revisit if the
   API ever accepts cookie-authenticated form posts from a different site, or if browsers
   relevant to users drop `Lax` defaults.

6. **Metrics are unauthenticated at `/metrics`.** Prometheus scrapes it from the internal network.
   Counters are per process; a multi-worker deployment needs `PROMETHEUS_MULTIPROC_DIR`.

7. **Audit log coverage.** Password resets are now audited. Logout and failed-login attempts are
   not, because login is the audited security event and failed attempts are already rate-limited
   and logged by the request-ID middleware.

## Open item (needs a decision, not made autonomously)
- **npm: `postcss` advisories bundled under `next` 15.5.27.** `npm audit --omit=dev` reports one
  high and one moderate finding. The only fix is a Next.js major upgrade (16.x), which is breaking.
  The CI step runs with `continue-on-error` until that upgrade is scheduled. Remove the flag when
  it lands.
- **Python runtime dependencies:** `pip-audit` clean at the time of this change; it blocks in CI.

## Verified
- Usage capture is covered by unit tests against both OpenAI-compatible clients.
- Retention and purge are covered by unit tests on real rows and files, including the
  foreign-key nulling case.
- The usage dashboard was exercised in a browser against the dev server, which surfaced a real bug
  (SQLite returns naive datetimes, and the comparison raised). A regression test now covers it.
