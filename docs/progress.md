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
