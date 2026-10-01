# Progress log

## Phase 0 — Scaffold (in progress, 2026-09-30)

**Built**
- Monorepo layout per PRD §4.2; `CLAUDE.md`; `docs/decisions/001` (local mode without Docker).
- API (`services/api`): FastAPI app factory, settings, JSON logging with request IDs,
  RFC 7807 errors, `/health` + `/ready` (DB + storage checks), SQLAlchemy base with portable
  types, local storage backend, shared enums (`app/core/enums.py`), Alembic baseline.
- Web (`apps/web`): Next.js 15 + Tailwind 4, sign-in and forgot-password pages
  (react-hook-form + zod), API client for problem+json, TanStack Query provider,
  dark/light theme, `/api/v1` proxy to the API.
- Makefile, `.env.example`, Dockerfiles, `docker-compose.yml`, GitHub Actions CI, pre-commit.

**Verified**
- API: 13 pytest tests pass; ruff + mypy strict clean; `alembic upgrade head` works;
  uvicorn serves `/ready` = ok.

**Verified on this machine (2026-09-30):** `make install`, `make lint`, `make test`, `make dev`
(API + web both serve, confirmed with curl). Docker Compose stack remains unverified (no
Docker on this machine either, see docs/decisions/001) — CI should be the first real check.
One pre-existing web bug fixed along the way: `vitest.config.mts` doesn't set `test.globals`,
so `@testing-library/react`'s auto-cleanup between tests never registered, leaking DOM across
tests. Fixed in `src/test/setup.ts` with an explicit `afterEach(cleanup)`.

Phase 0 closed.

## Phase 1 — Auth, RBAC, Admin: types & defaults (done, 2026-09-30)

**Built**
- Real team templates received and placed at `templates/source/` (git-ignored, per
  docs/decisions/001-style handling of internal bank data) — `QA_Test_Cases_Template.xlsx`
  and `QA_Test_Report_Template.docx`. Confirmed the xlsx matches PRD §3.1 exactly: banner rows
  12/44, 31 default rows, fills/fonts/column widths all as documented.
- Auth: argon2 password hashing, JWT access (15 min) + refresh (7 day) tokens as httpOnly
  cookies (not returned in the response body — the SPA never needs to read them, so keeping
  them out of JS reach closes off XSS token theft), login/refresh/logout/me, forgot/reset
  password (reset link logged server-side for now — no email service configured yet), login
  rate limiting (5/min, in-process — fine for a single server, needs Redis for multi-worker).
- RBAC: `require_admin`/`require_user` dependencies; every admin endpoint has an RBAC test
  (401 anonymous, 403 non-admin) via a parametrized matrix in `test_rbac.py`.
- Admin: test case types (CRUD, duplicate, deactivate-vs-delete), default test cases (CRUD,
  reorder, version bump on edit per ADM-DC-6), users (create/patch/reset-password).
- `services/docengine/xlsx_importer.py` (ADM-DC-3): parses the DEFAULT SCENARIOS section from
  a template-format workbook — detects columns from the header row (not hard-coded letters),
  un-merges FEATURE *and* STEPS columns (the real template merges both — PRD §3.1 calls out
  STEPS merging as optional but the real file does it for Session Timeout etc.), warns on
  duplicate TESTCASE NO and missing values instead of crashing.
- `app/cli.py`: `seed-admin` and `seed-defaults` (imports the real template's 31 defaults into
  a "Web Application" type, idempotent).
- Admin console UI: types list, type detail with a defaults grid (add/edit/delete/reorder via
  up-down buttons/import-from-xlsx/export-to-CSV/duplicate-type/deactivate/delete), users list
  with role/active/reset-password. Workspace shell + placeholder dashboard. Reset-password page.
- Audit log (`audit_log` table) written on every admin create/update/delete/import/login.

**Simplifications vs. the PRD, deliberate for Phase 1:**
- Defaults reorder uses up/down buttons, not drag-and-drop (ADM-DC-2 says "drag-and-drop
  reorder" — ended up with a simpler control since no DnD library was in the repo yet; same
  end state, revisit if the team wants true DnD).
- Bulk export (ADM-DC-4) is CSV only; the styled xlsx export reuses the Phase 2 doc engine
  once it exists, so it wasn't duplicated here.
- ADM-UP-2 ("admin sees all projects, can reassign ownership") deferred to Phase 3 — there's
  no `projects` table yet (PRD §16 puts Projects in Phase 3).

**Bug caught during browser verification:** uploading the *real* template 500'd — the real
file merges STEPS cells across rows that share identical steps (e.g. the Session Timeout
Usability rows), which PRD §3.1 documents as optional/sometimes-present. The importer only
un-merged FEATURE, so merged-away STEPS cells parsed as `[]`, failing
`DefaultTestCaseIn`'s `min_length=1`. Fixed by generalizing the merge-lookup to any column and
added a defensive fallback (warn + placeholder text) for any row that's still empty after
that, so a malformed template warns instead of 500ing. Regression tests added. Re-verified via
a full Playwright run against the real file: 31 cases, correct feature breakdown, 0 warnings,
0 console errors.

**Verified**
- 91 pytest tests (was 13 at the end of Phase 0), ruff + mypy --strict clean.
- 10 vitest tests, eslint + prettier + tsc --strict clean, production build succeeds.
- Full browser walkthrough (Playwright, screenshots in this session's scratchpad): login →
  dashboard → create type → add/edit/reorder default cases → bulk-import the real template →
  create a second user. Zero console errors throughout.

## Phase 2 — Document engine (done, 2026-10-01)

**Built**
- `docengine/xlsx_writer.py`: fills the real `QA_Test_Cases_Template.xlsx` from suite data.
  Rows 1–11 (header block + table headers) are never touched beyond overwriting value
  cells — they already ship correctly styled. Rows 12+ are cleared and rewritten with styles
  captured from the template's own banner/body/id/evidence cells before deletion. Writes
  live `COUNTIF` formulas for Result Analysis (E2:E8), a hidden helper column I for the
  Regression count, FEATURE-column merges within each section (never across the banner),
  and evidence sheets (created lazily per evidence group, Pillow-resized images, internal
  hyperlinks in the `'{sheet}'!A{n}` format Appendix B specifies).
- `docengine/docx_tokenizer.py` + `docx_writer.py`: turns the raw `QA_Test_Report_Template.docx`
  into a docxtpl-tagged working copy, then renders it. Two non-text things needed real XML
  surgery: the "Is this build certified…" line is a flattened *image*, not text (replaced
  with a real ☒/☐-rendering text run); the Comments/Observation body text turns out to be
  real text too, but inside a DrawingML text box invisible to `paragraph.text` (clearing that
  paragraph's runs removes it, and PRD §3.2's stray "s" typo, together). Three Approvals rows
  also carried real signature images from whoever filled in the sample — dropped as personal
  data specific to one filled report, not template content.
- `templates/tokenized/QA_Test_Report_Template.docx` — the generated, committed, bank-data-free
  working copy. Regenerate with `make -C services/api` → `uv run python -m app.cli
  tokenize-report-template` (or `python -m app.cli tokenize-report-template`) if the source
  template ever changes.
- Admin template management (`routers/admin/templates.py`, ADM-TM-1/3/4): upload xlsx/docx,
  validated immediately by actually rendering it against fixture data (a template can't be
  activated if that render fails — caught at upload time, not weeks later on a real export);
  docx templates are auto-tokenized on upload (ADM-TM-2's "automated tokeniser" path — the
  manual download/re-upload path from the PRD isn't built); activate/archive/delete; preview
  returns the rendered native file (xlsx/docx) rather than a PDF, since LibreOffice isn't
  installed on this machine (see below).

**Real bug caught by testing against the actual files, not assumptions:**
docxtpl's `{%tr %}`/`{%p %}` row/paragraph-loop tags collapse their *entire* enclosing
row/paragraph down to the bare Jinja tag (confirmed by reading docxtpl's `patch_xml` source
after a render blew up with a Jinja syntax error). The natural-looking approach — put
`{%tr for %}` in the first cell of the data row and `{%tr endfor %}` in the last — silently
destroys the data row. Fixed by giving each loop its own dedicated row/paragraph (for-tag,
content, endfor-tag as three siblings), verified with an isolated minimal docxtpl repro
before touching the real tokenizer. A second real bug: the PR Links/Version Number cells in
the raw template hold one paragraph per line — an early version only cleared
`cell.paragraphs[0]`, leaving the original Kusala URLs mixed into the rendered output
alongside the fixture data. Fixed by clearing every paragraph in the cell first.

**Deferred, documented, not silently dropped:**
- No LibreOffice on this machine → xlsx formulas are written correctly but not
  pre-calculated (Excel computes them the moment it's opened — this is normal, expected
  Excel behavior, not a defect), and template preview returns the native file instead of a
  PDF. Tests needing LibreOffice are marked `needs_libreoffice` and skip cleanly here; the
  Phase 0 scaffold already anticipated this (the marker existed before Phase 2 started).
- Admin UI for template upload/activate isn't built yet (backend + tests only) — types/users
  got a UI in Phase 1, templates didn't, given how much ground Phase 2's backend already
  covered. Flagging so it doesn't get lost.
- Full suite xlsx *import* (round-trip, for USR suite import) isn't built — only the
  DEFAULT SCENARIOS slice (ADM-DC-3, done in Phase 1) exists. Natural Phase 3/4 territory
  once the suite domain model exists.

**Verified**
- 132 pytest tests (was 91 at the end of Phase 1: +9 xlsx golden, +13 docx golden, +7 admin
  templates, +9 xlsx importer regression/defensive tests, +5 RBAC), 1 skipped
  (`needs_libreoffice`), ruff + mypy --strict clean.
- Golden tests run against the *real* team templates (not just synthetic fixtures), gated to
  skip gracefully in CI where the git-ignored source files aren't present.

Phase 2 closed.

## Phase 3 — Projects, suites, generation (done, 2026-10-01)

**Built**
- AI layer (`services/ai/`): provider-agnostic `LLMClient` protocol — `OpenAICompatibleClient`
  (DeepSeek, since the user wants that for now and Anthropic once a production key exists —
  docs/decisions/004) via the `openai` SDK pointed at DeepSeek's base URL, `AnthropicClient`
  (wired but unexercised, no key yet), `FakeLLMClient` (PRD §13.3, used by every automated
  test). `structured.py` validates every call against a Pydantic schema with one automatic
  repair retry. `masking.py` masks NUBAN/BVN-NIN/card-PAN(Luhn)/email/phone before any story
  text reaches a model — order matters, since an 11-digit Nigerian phone number and a BVN/NIN
  are the same length and the more specific pattern has to run first or it never fires.
- Ingestion (`services/ingestion/extract.py`): docx/pdf/txt/md/xlsx/csv → plain text.
  Image-based story pages (OCR) aren't implemented — that needs a vision-capable call, out of
  scope on a text-only chat API.
- Generation pipeline (`services/ai/{analyze,generate,postprocess,orchestrator}.py`):
  analyze → generate per feature → normalize wording → BVA completeness (USR-GEN-5) →
  approval-chain completeness (USR-GEN-6) → one gap-fill top-up call if anything's missing →
  traceability check → duplicate detection (`difflib` similarity, no embedding model
  available). Prompts are versioned files in `services/ai/prompts/`.
- Data model: `projects` (owner + members, PRD §7.1's "owns or is a member of" access rule),
  `user_stories`, `test_suites` (snapshots the type's defaults at creation per ADM-DC-6),
  `test_cases`, `generation_jobs`.
- Continuous case numbering (`services/suites/numbering.py`, USR-GEN-2/3): `<prefix>_<NNN>`
  across default + functional sections, recomputed on every include-toggle/add/delete.
- In-process background generation (`services/suites/generation_runner.py` +
  `job_events.py`): `POST /suites/{id}/generate` spawns a thread (matches the Phase 0
  no-Redis decision), SSE at `GET /jobs/{id}/events` streams per-feature progress.
- Full API surface: projects/stories/suites/cases CRUD, generate, refresh-defaults, cycles,
  and `/suites/{id}/export/xlsx` — reuses the Phase 2 `xlsx_writer` directly, preferring an
  admin-activated `Template` row over the raw source file if one exists.
- Frontend: Projects list/detail (story upload/paste), suite setup page, and the suite
  workspace page (defaults grid, story selection, SSE-streamed generation progress,
  functional-cases grid, xlsx download).

**Two real bugs caught by testing, not just reasoning about the code:**
1. `renumber_suite_cases` queried `TestCase` rows immediately after `db.add()`-ing them, but
   the app's sessions run with `autoflush=False` — the query didn't see the pending inserts,
   so every newly created suite's defaults came back with blank display IDs. Caught by an
   integration test, not by reading the code. Fixed with an explicit `db.flush()`.
2. Browser-testing the actual "no AI key configured" failure path (the real state this app
   will be in until the user adds a DeepSeek key) showed "Failed: unknown error" instead of
   the real message. The SSE endpoint has two paths — live events via the pub/sub queue, and
   a replay branch for when the job already finished before the client subscribed (very easy
   to hit: a FakeLLM failure is near-instant). The replay branch only sent `{type, status}`,
   dropping `error` entirely. Fixed, and added a regression test — the two existing
   assertions on the job's DB row would never have caught this, since the bug was specifically
   in what got replayed over SSE, not in what got stored.

**Deferred, documented, not silently dropped:**
- Row actions PRD asks for — regenerate a single case, "generate more like this" per feature,
  duplicate/move a row, bulk status actions, evidence upload — aren't built. Include-toggle
  and delete are.
- Admin UI for AI/execution settings (ADM-AI-*, ADM-EX-*) isn't built; model names and the
  DeepSeek key come from `.env`/`Settings`, not a database-backed admin page.
- Live DeepSeek smoke test (PRD's Phase 3 DoD item) needs `DEEPSEEK_API_KEY` in `.env`, which
  the user will add themselves — the pipeline is ready for it (`ai_provider=deepseek` flips
  it on), verified so far against `FakeLLMClient` only.
- Bugs CRUD, the full suite-execution status workflow, and reports are Phase 4.

**Verified**
- 211 pytest tests (was 132 at the end of Phase 2), 1 skipped (`needs_libreoffice`), ruff +
  mypy --strict clean.
- Full browser walkthrough: login → create project → paste a story → set up a suite → all 31
  defaults render correctly numbered → attempt generation (fails cleanly with the real error,
  post-fix) → xlsx export downloads successfully. Zero console errors throughout.

**Next**
Phase 4 — Suite execution (manual) & reports.

## Phase 4 — Suite execution (manual) & reports (2026-10-01)

**Built**
- Models: `Evidence`, `Bug`, `ReportDefaults` (singleton), `NoteSnippet`, `Report`
  (`services/api/app/models/`), one Alembic migration.
- Execution UI on the case card: status select, regression checkbox, actual-result field,
  evidence (file picker + paste-to-upload), and a "File bug" action that appears once a case
  is marked Failed and drafts a bug from the case's scenario/steps/expected/actual.
- Bulk actions: `POST /suites/{id}/cases/bulk` ("Mark all as Passed" in the UI).
- Bugs: full CRUD + status workflow (open/fixed/retested/closed), suite-scoped
  (`app/routers/bugs.py`, `bugs-panel.tsx`).
- Reports (`app/routers/reports.py`, `app/services/reports/builder.py`): draft → edit → render
  .docx, versioned. Result Analysis, automation ratio, bug counts, and the certified-suggestion
  are computed deterministically from the same "included cases" filter the xlsx export uses, so
  USR-RP-3 (report numbers = xlsx numbers) holds by construction, not by a reconciliation step.
  AI drafts feature descriptions/exceptions/comments; render re-checks the numbers against the
  suite's current state and 409s on drift, with an explicit, audit-logged override
  (`ra_overridden` + required `ra_override_reason`) for when the user has verified manually.
- Admin: report defaults (exit criteria, approval roles, classification label) and reusable
  comment snippets, seeded via `make seed-report-defaults`.
- Frontend report editor (`reports/[id]/report-detail-client.tsx`): full editable form over
  every report field, Save draft, Download .docx.

**One real bug caught by browser testing, not by the test suite:**
`draft_suite_report` wraps the AI drafting call in `except (LLMError, ValidationError)` and is
supposed to fall back to deterministic placeholder text so the user still gets an editable
report even when the AI call fails — this was built specifically for the DeepSeek
insufficient-balance state this project has been in all session. But `OpenAICompatibleClient
.complete_json` and `AnthropicClient.complete_json` never actually caught the provider SDKs'
own exceptions (`openai.APIStatusError`, `anthropic.APIError` — covers auth errors, rate
limits, insufficient balance, network failures) and wrapped them as `LLMError`; only the
narrow "empty response" case raised `LLMError`. So the one real failure this app currently
produces bypassed the fallback entirely and 500'd — found by actually clicking "Generate
Report" in a live browser against the real DeepSeek key, not by reasoning about the code or
by the (`FakeLLMClient`-only) test suite, which had no way to exercise this path. Fixed by
catching the SDK base exceptions inside both clients' `complete_json` and re-raising as
`LLMError`; added `tests/unit/test_ai_client.py` asserting a mocked `402` becomes `LLMError`.

**Deferred, documented, not silently dropped:**
- Automated test execution / CI-triggered runs (PRD's "execution (manual)" scope for this
  phase explicitly excludes automation) — manual-only, as scoped.
- Evidence kinds beyond screenshots (request logs, video) have the enum but no upload path
  yet — only image evidence is wired into the UI and the xlsx evidence sheet.
- Test cycles (re-running a suite as cycle 2, 3, ...) — `test_cycle` exists on `TestSuite` and
  feeds Result Analysis, but there's no UI action to increment it yet.

**Verified**
- 267 pytest tests (was 266 at the end of Phase 3, +1 for the LLMError regression), 1 skipped,
  ruff + mypy --strict clean. Frontend: typecheck/lint/format/`next build` all clean.
- Full browser walkthrough (Playwright, headless, against the real dev DB and a live
  DeepSeek key): login → suite with 31 default cases → mark a case Failed → file a bug from
  it → upload evidence via file picker → bulk "Mark all as Passed" → download xlsx (verified
  non-empty) → "Generate Report" (hit and fixed the bug above) → edit the product name →
  save → download .docx (verified the template rendered with the edited product name, correct
  certified=No checkbox state, and correct bug/result-analysis numbers reflecting both the
  bulk-pass and the still-open bugs). Zero console errors or 5xx responses on the final run.

**Next**
Phase 5 — Test Lab: Web (agent mode + script mode, deterministic defaults run against
`infra/demo-target`).

## Phase 5 — Test Lab: Web (2026-10-01)

**Built**
- `infra/demo-target/` (PRD §13.6): a tiny FastAPI app — login (valid/invalid/blank/lockout),
  a session-gated dashboard, logout, fixed security headers — used as the Web runner's target
  by both the deterministic routines and the live integration tests. Not a product; a stable
  fixture.
- Secrets (`app/models/secret.py`, `app/core/crypto.py`): project-scoped, write-only
  credentials, Fernet-encrypted at rest (explicit `SECRETS_KEY` in any shared environment; a
  deterministic dev fallback derived from `jwt_secret` otherwise, so local dev needs no extra
  `.env` value — docs/decisions/001's spirit). Never returned in any response.
- Execution engine (`app/services/execution/`):
  - `agent_client.py` — a tool-calling client (DeepSeek/OpenAI-compatible function calling;
    Anthropic explicitly not implemented, same scope cut as docs/decisions/004, now also
    documented as the right call by docs/decisions/005's lesson — an untested stub is a worse
    failure mode than a clear error).
  - `tools.py` — Playwright-backed tools (`navigate`, `snapshot`, `click`, `fill`, `select`,
    `press`, `wait_for`, `assert_visible`, `assert_url`, `back`, `go_idle`), URL-allowlisted,
    addressable by either a `snapshot()` ref or a raw CSS selector (docs/decisions/006).
  - `agent.py` — the agent loop (PRD §8.4): system prompt, per-step `RunStep`-shaped events,
    `fill`'s `secret_ref` resolved server-side and never put in any message sent to the model
    or stored in any log.
  - `deterministic.py` — built-in routines (login valid/invalid, blank fields, logout+back,
    security headers) selected by a tag on `default_test_cases.tags` (reuses the existing
    field rather than adding an ADM-DC-7 "Automatable" column/admin UI — out of scope here).
  - `script_mode.py` — freezes a passing agent run's tool calls (never a resolved secret
    value) into `TestCase.automation_script`; replays without the LLM; self-heals to agent
    mode on replay failure.
  - `execution_runner.py` — orchestrates a run: fresh browser context per case, script mode →
    deterministic routine → agent mode in that order, SSE progress (`run_events.py`,
    cooperative cancellation between cases).
- API: `CRUD /secrets`, `POST /runs`, `GET /runs/{id}`, `GET /runs/{id}/steps`,
  `GET /runs/{id}/events` (SSE), `POST /runs/{id}/cancel`, `POST /runs/{id}/apply`,
  `GET /suites/{id}/runs`.
- **Review-before-apply** (PRD §7.6, §15's "AI marks a failing test as passed" risk): a run's
  per-case verdict lives only in `TestRun.summary_json` until `POST /runs/{id}/apply` writes
  `status`/`actual_result`/`execution_mode`/`last_run_id` onto the `TestCase` row. Evidence
  screenshots ARE attached live (needed for the live view and the step audit trail) — scoped
  deliberately to gate the verdict, not supporting images; documented in
  `execution_runner.py`'s own docstring.
- Frontend: a "Run in Test Lab" selection on each case card + a Test Lab panel on the suite
  page (target URL, start run, past-run history); a run detail page (`/runs/[id]`) with a live
  SSE log while running, a per-case results/apply view once finished, and a full step log with
  screenshot thumbnails; a Secrets panel on the project page.

**Four real bugs caught by testing, not reasoning about the code:**
1. `infra/demo-target`'s `/login` and `/dashboard` routes return `HTMLResponse | RedirectResponse`
   — FastAPI can't build a Pydantic response model for a Response-subclass union and raised
   `FastAPIError` at route-registration time. Never caught until the first live Playwright test
   actually imported and ran the app (nothing before Phase 5 had executed this file at all).
   Fixed with `response_model=None` on both routes.
2. `BrowserTools._locator` only ever wrapped its argument as a `[data-qa-ref="..."]` snapshot
   ref — every deterministic routine (written against real CSS selectors like `#username`)
   timed out against a real page, because `#username` became the nonsensical selector
   `[data-qa-ref="#username"]`. The fake-tools unit tests couldn't catch this (they don't model
   real selector resolution); only the live Chromium + demo-target integration tests could.
   Fixed by shape-detecting snapshot refs (`^e\d+$`) vs. passing anything else straight to
   `page.locator()` — docs/decisions/006.
3. The `logout_back_button` routine legitimately failed on first run: demo-target's dashboard
   had no `Cache-Control` header, so the browser's back/forward cache restored it after logout
   even though the server-side session was gone. A real finding, not a test bug — fixed by
   adding `Cache-Control: no-store, must-revalidate` to the dashboard response, which is what
   a real authenticated page should send regardless.
4. `POST /runs/{id}/apply` looked correct and passed a 200 — but silently never persisted
   `applied: true`. `case_results = dict(cases_field)` only shallow-copies the outer dict; the
   nested per-case dicts stayed the same objects already referenced by `run.summary_json`, so
   mutating `result["applied"] = True` also mutated the "old" value SQLAlchemy's dirty-check
   compares against. Old and new ended up `==`, no UPDATE was ever issued, and `db.refresh()`
   silently restored `applied: false`. Caught only by the full live integration test asserting
   on the *response body* of a second read, not just the 200 status. Fixed with
   `copy.deepcopy`.

**Deferred, documented, not silently dropped:**
- API and Android targets (Phase 6/7 per the PRD's own plan) — the UI's `target` is fixed to
  `web`; `POST /runs` 400s on anything else.
- Standalone "exploratory run" (guidance-only, no suite, "Save as suite" later) — runs require
  a `suite_id` and at least one existing case in this phase.
- Manual OTP / 2FA pause (`POST /runs/{id}/input`) — not built; `go_idle` and the allowlist are
  the only session-related tooling so far.
- ADM-DC-7's admin-configurable "Automatable" hint/selector UI — deterministic routines are
  selected via a tag convention on the existing `tags` field and are hard-coded against
  `infra/demo-target`'s markup specifically; running one against an arbitrary project URL
  isn't implemented.
- Evidence from a run that's never applied stays attached to the case (visible in exports)
  until deleted by hand — see the review-before-apply note above.

**Verified**
- 326 pytest tests (was 267 at the end of Phase 4, +59: crypto, agent loop, deterministic
  routines, script mode — all with fake doubles — plus live Playwright + real demo-target
  integration tests for `BrowserTools`, every deterministic routine, and the full
  run → apply → evidence flow), 1 skipped, ruff + mypy --strict clean. Frontend
  typecheck/lint/format/build clean, 10 vitest tests passing.
- Full browser walkthrough (Playwright, headless, against the real dev DB): login → project
  with a secret → suite created from a type with a `deterministic:login_valid`-tagged default
  → select the case for a Test Lab run → live view while running → results with the case
  Passed → Apply → confirmed in the database that the case's status/actual_result/
  execution_mode/last_run_id were written, and that a real evidence screenshot (valid PNG) was
  attached. Zero console errors or 5xx responses.

**Next**
Phase 6 — Test Lab: API (OpenAPI/Postman/cURL parsing; generated + executed cases against a
Prism mock; masked request/response logs as evidence images; Postman/pytest export).

## Phase 6 — Test Lab: API (2026-10-01)

**Built**
- `infra/demo-api/` (PRD §13.6, scope note in docs/decisions/007): a small real FastAPI
  "petty cash transfers" API — Bearer auth, a transfer limit, idempotent-by-reference creates,
  owner-scoped reads (IDOR-testable) — standing in for the PRD's suggested Prism-from-a-spec
  mock, since a real app's own `/openapi.json` is both the spec source and a genuinely
  stateful target, which a static mock can't be for categories like idempotency and IDOR.
- Spec parsing (`app/services/execution/api_spec.py`, `POST /api-specs/parse`): OpenAPI
  (JSON/YAML, local `$ref` resolution), Postman collection v2.1 (recursive folder walk), and
  pasted cURL commands, all normalized to the same `EndpointCatalogue`.
- AI generation (`app/services/ai/generate_api.py`, `POST /suites/{id}/generate-api-cases`):
  one call per selected endpoint, producing both the human-readable case (feature/scenario/
  steps/expected, across the PRD's 11 API test categories) and its compiled, executable
  `RequestPlan` in the same structured call — unlike Web, API execution is always
  deterministic httpx once a case has a plan, so there's no separate analyze-then-generate
  split or agent-mode ambiguity to design for.
- Execution (`app/services/execution/api_runner.py`, `api_execution_runner.py`): `{{var}}`
  chaining across cases in a run (an earlier case's `extract`ed values feed a later case's
  path/headers/query/body **and assertions**), assertions (status/JSON-path/schema/header/
  latency), masked request+response logs rendered to a monospace PNG (`log_image.py`) for the
  xlsx evidence sheet **and** stored as a separate text evidence file — both artifacts PRD
  §7.6.2 step 5 asks for. Reuses the Phase 5 run/apply/SSE/cancel infrastructure (`TestRun`,
  `RunStep`, review-before-apply) almost entirely unchanged — only the orchestration loop
  (httpx instead of Playwright, one step per case instead of many) and the target-dispatch in
  `POST /runs` are new.
- Export (`app/services/docengine/api_export.py`): Postman collection v2.1 and a pytest file,
  generated from a suite's API-section cases.
- Frontend: an API-spec-to-test-cases panel (source picker, file/URL/cURL input, parsed
  endpoint checklist, guidance, generate) and a Target (Web/API) selector on the suite's Test
  Lab panel; the existing run detail page (live SSE log, results/apply, step log with
  thumbnails) needed no changes — it was already generic enough to render API runs correctly.

**Two real bugs caught by testing, not reasoning about the code:**
1. The Postman parser's query-param extraction called `.get("query")` on `request.url` before
   checking it was actually an object — Postman also allows a plain string URL, which has no
   `.get`. Would have crashed the whole parse on any collection using the simpler string form,
   not just skipped that one request's params. Caught by mypy's `union-attr` check, not a
   test — a reminder that `mypy` catches real bugs here, not just style noise.
2. Assertion `expected` values never received `{{var}}` substitution — only `path`/`headers`/
   `query`/`body` did. A chained assertion like "the fetched record's id equals the id the
   create step extracted" could never pass: it compared the real value against the literal,
   unsubstituted string `"{{transfer_id}}"`. Invisible in the unit tests (none of them chained
   an assertion across cases) — only the live integration test running a real create → fetch →
   assert-the-id-matches flow against `infra/demo-api` caught it. Fixed by substituting
   `expected` the same way as every other field, plus a new unit test pinning the exact
   behavior so the fix can't silently regress.

**Deferred, documented, not silently dropped:**
- Android (Phase 7 per the PRD's own plan).
- OAuth2 client-credentials auth (PRD lists it as an input option) — only Bearer/API-key-via-
  header style auth is exercised, via `{{secret_name}}` substitution in headers; a case needing
  a token-URL exchange first would need to be hand-built as a two-case chain today.
- `response_time` category assertions (`latency_below_ms`) are implemented in the runner but
  the generation prompt is told to use them "sparingly, only when asked" — no default coverage.
- Jira/Azure DevOps bug export (PRD's "API integration v2") — out of scope for this phase, same
  as Phase 4/5's bug handling.

**Verified**
- 362 pytest tests (was 326 at the end of Phase 5, +36: spec parsers for all three formats,
  the request-plan runner including the assertion-substitution regression test, plus live
  integration tests against a real `infra/demo-api` — spec parsing from its real
  `/openapi.json`, AI generation with `FakeLLMClient`, and a full create→chain→auth-missing
  run → apply → evidence flow), 1 skipped, ruff + mypy --strict clean. Frontend
  typecheck/lint/format/build clean, 10 vitest tests passing.
- Full browser walkthrough (Playwright, headless, against the real dev DB and a live
  `infra/demo-api` process): parsed the live app's own OpenAPI spec through the UI (all three
  real endpoints appeared, correctly labeled) → added a project secret → started an API-target
  run on a seeded case (AI generation itself untested live — DeepSeek remains out of balance
  this session, same known state as Phase 4/5 — the generation *code path* is covered by the
  `FakeLLMClient` integration test instead) → watched it pass → applied → confirmed in the
  database that the case was updated and that both evidence files (PNG render + text log)
  were written with the secret correctly masked out of the stored log. Zero console errors or
  5xx responses.

**Next**
Phase 7 — Test Lab: Android (APK upload & analysis; emulator run of a sample APK with
evidence; crash detection; provider interface for remote device farms).

## Phase 7 — Test Lab: Android (2026-10-01)

**Built**
- `infra/demo-android/ApiDemos-debug.apk`: Appium's own `android-apidemos` fixture, committed
  as a binary (docs/decisions/008) — real multi-screen native navigation to exercise the
  runner against, since hand-building an APK from scratch needs a full Gradle/signing
  toolchain this repo doesn't have.
- APK upload & analysis (`app/models/apk.py`, `apk_analysis.py`, `POST /projects/{id}/apks`):
  shells out to `aapt dump badging` to extract package name, launch activity, version — shown
  to the user immediately (the project page's new Android APKs panel) rather than only at run
  time, per PRD's "shown for confirmation."
- `AndroidDeviceProvider` (PRD's explicit interface ask): `LocalEmulatorProvider` (v1,
  implemented and live-verified) identifies a usable emulator by asking each attached device
  which AVD it's running, never just grabbing the first one off `adb devices` — boots a fresh
  instance of the configured AVD if none is already warm. `RemoteAppiumProvider` (cloud device
  farm) stays an explicit `NotImplementedError` stub — no farm account to build and verify
  against, and docs/decisions/005 already covered why an unverified implementation is worse
  than a clear stub.
- `AndroidTools` (`android_tools.py`, PRD §7.6.3's tool set — `snapshot`, `tap`, `type`,
  `swipe`, `scroll_to`, `back`, `home`, `launch_app`, `background_app`, `rotate`, `wait_for`,
  `assert_visible`) over the real Appium Python client / UiAutomator2, addressing elements by
  a ref assigned to interactive nodes in the UiAutomator XML dump, tapped at the bounds
  center — the same "assign a ref to what the model can act on" shape as Web's `data-qa-ref`,
  adapted since UiAutomator XML has no selector equivalent.
- `android_agent.py`: a second, independent agent loop (not a refactor of Web's `agent.py`
  into a shared engine) — the tool sets differ enough in their arguments that sharing would
  need as much per-target parameterization as it'd save, and this keeps Phase 5's
  already-verified Web loop untouched. `CaseStepEvent`/`CaseRunResult` (genuinely generic) are
  reused as-is.
- `android_execution_runner.py`: installs the APK once per run (not per case — PRD's
  "fresh app relaunch per case" is satisfied by force-stop + Appium relaunch, which is cheap;
  reinstalling a multi-MB APK before every case isn't), force-stops + clears logcat before
  each case, runs the agent loop, then checks logcat for `FATAL EXCEPTION`/`ANR in` referencing
  the app's package and **auto-fails the case regardless of the agent's own verdict** — PRD
  §7.6.3's explicit requirement, verified for real by deliberately crashing the app
  mid-case (`adb shell am crash`) against a fake agent that confidently reports "Passed."
  Uninstalls the APK when the run ends either way.
- Frontend: an Android APKs panel on the project page (upload, see analyzed metadata, delete),
  and a third Target option (Android) on the suite's Test Lab panel with an APK picker in
  place of the target-URL field — the existing run detail page needed no changes.

**Three real bugs caught by testing against a real emulator, not reasoning about the code:**
1. `BrowserTools`-style `_locator` reasoning doesn't apply to Android at all, but an analogous
   mistake did: the first version of the live test fixture reinstalled the APK and opened a
   brand-new Appium session before *every single test function*. In practice this was flaky —
   one run landed on the home launcher instead of the app, another timed out talking to the
   device entirely. Fixed by installing once per test module and using force-stop + relaunch
   between tests, which is exactly what the real runner does between cases — the fixture was
   wrong, not just slow, and fixing it to match production behavior made both reliable.
2. The crash-detection regex matched a logcat line correctly, but the check required the
   crashing app's **package name on the same line** as `FATAL EXCEPTION` — real crash logs
   never put them on the same line (`FATAL EXCEPTION: main` is one line; `Process:
   <package>, PID: <n>` is the next). The very scenario this feature exists for — PRD's
   "auto-fail the case on crash" — silently failed to fire, confirmed only by deliberately
   crashing the real app via `adb shell am crash` and watching the case come back "Passed"
   from the agent's own (wrong) self-report. Fixed by matching the crash marker and then
   checking a short window of following lines for the package name, verified against the
   actual captured logcat output before re-running the test.
3. (Caught by mypy, not a test, but worth noting alongside the others) the Postman-collection
   parser's query-param extraction in Phase 6 had an identical "trust the shape before
   checking it" bug — see that phase's own entry — same root cause as #1 above: code that
   looks fine until it's handed a real malformed/unexpected case.

**Deferred, documented, not silently dropped:**
- `.aab` → universal-APK conversion via bundletool — only `.apk` uploads are accepted.
- Manual OTP/2FA pause (`POST /runs/{id}/input`) — same gap as Web/API; `background_app` is
  the only session-timeout-adjacent tool so far.
- Device profile picker — fixed to whatever `ANDROID_AVD_NAME` is configured to; PRD's
  "Pixel-class, API 33/34 default" is a setup-time choice, not a per-run one, in this phase.
- Permissions auto-grant is always on (`autoGrantPermissions=True`) rather than a per-run
  toggle.
- Script mode (record a passing agent run, replay without the LLM) — built for Web
  (docs/progress.md Phase 5), not extended to Android. PRD doesn't ask for it explicitly for
  Android and the agent loop is cheap enough per-case here that it wasn't an obvious need yet.

**Verified**
- 391 pytest tests (was 362 at the end of Phase 6, +29: APK analysis, the device-provider's
  isolation guarantee with mocked `adb`, the Android agent loop with fake tools, plus live
  integration tests against a real emulator — `AndroidTools` driving the real ApiDemos app,
  and a full run → apply → evidence flow including the deliberate-crash auto-fail test), 1
  skipped, ruff + mypy --strict clean. Frontend typecheck/lint/format/build clean, 10 vitest
  tests passing.
- Full browser walkthrough (Playwright, headless, against the real dev DB, a real emulator,
  and a real Appium server): uploaded the APK through the UI and watched it get analyzed
  live → created a suite → selected the Android target and the uploaded APK → started a run →
  watched the live view → reached Results → Applied. The run itself ended Blocked (DeepSeek
  remains out of balance this session, the same known, unrelated state as every prior phase)
  — but the failure path was exactly as designed: a clear per-case error message, a populated
  step log, and a suite update the user could still review and apply. Zero console errors or
  5xx responses.
- Device isolation verified on the actual development machine, which had a second, unrelated
  emulator already running: `LocalEmulatorProvider` never touched it, confirmed both by the
  mocked unit tests and by directly inspecting `adb devices` throughout this phase's work.

**Next**
Phase 8 — Hardening (security checklist per PRD §12, complete audit log, usage dashboard,
retention jobs, measured performance targets, user & admin guide in `docs/`).
