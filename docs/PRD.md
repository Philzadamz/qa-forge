# PRD: QA Forge — AI-Assisted Test Case Generation, Reporting & Test Execution Platform

> **Working name:** QA Forge (rename freely — search/replace `qa-forge` / `QA Forge`).
> **Owner:** Adamz (Theophilus A. Inaede), Senior QA Engineer / SDET
> **Audience:** Claude Code (build agent) + QA team
> **Status:** v1.0 — ready for implementation
> **Source templates (must be committed to the repo before build starts):**
> - `templates/source/QA_Test_Report_Template.docx` ← from `Branch_Petty_Cash_Retirement_Flow_on_Kusala_QA_Test_Report.docx`
> - `templates/source/QA_Test_Cases_Template.xlsx` ← from `Petty_Cash_Retirement_QA_Test_Cases__.xlsx`

---

## 0. How to use this PRD with Claude Code

1. Create an empty repo, copy this file to `docs/PRD.md`, and copy the two template files into `templates/source/` with the names above.
2. Start Claude Code in the repo and say:
   *"Read docs/PRD.md fully. Build the project phase by phase as defined in Section 16. Do not start a phase until the previous phase's acceptance criteria pass. After each phase, run the tests and summarise what was built."*
3. Section 16 lists each phase with its own "Definition of Done". Section 17 gives a ready-made `CLAUDE.md` to drop in the repo root so every Claude Code session keeps the same rules.
4. **Golden rule for the build agent:** the team's templates are the source of truth for output formatting. Generated `.xlsx` and `.docx` files must look like the team's own files filled in by hand — same fonts, colours, column widths, merged cells, table layouts, footer and classification label. Never regenerate these documents from scratch with a generic layout.

---

## 1. Problem & Goals

### 1.1 Problem
QA engineers on the team spend a large share of each project on repetitive documentation work:
- Re-typing the same **default (non-functional/security/usability) scenarios** — Login, 2FA, Logout, Session Timeout, Exception Logging, Audit Trail, Encryption, Usability, Injection, Broken Authentication, Security Misconfiguration, Broken Access Control — into every new test-case workbook.
- Manually deriving **functional test cases** from user stories/BRDs (boundary values, role routing, approval chains, validation rules).
- Manually filling the **QA Test Completion Report** (.docx) — counting passes/failures, copying feature lists, writing observations, filling approvals.
- Manually executing tests and pasting **screenshots as evidence** into per-feature evidence sheets, then hyperlinking each test case to its evidence.

### 1.2 Goals
| # | Goal | Measure |
|---|------|---------|
| G1 | Admin maintains one central library of default test cases per test-case type | Admin can create/edit/reorder/deactivate defaults; changes reflect on next generation |
| G2 | Users generate a complete test-case workbook (defaults + AI functional cases) from a user story in minutes | < 3 min from upload to downloadable `.xlsx` for a typical story |
| G3 | Output files match the team's existing templates exactly | Visual diff check passes (Section 13.4); reviewers can't tell it from a hand-filled file |
| G4 | Users generate the QA Test Completion Report from a test suite's results | Metrics auto-computed; report downloadable as `.docx` in template format |
| G5 | Users can run AI-driven tests on Web, API and Android targets, with evidence captured automatically | Results and screenshots flow back into the suite and into both output files |
| G6 | Secure enough for fintech/banking QA environments | RBAC, encrypted secrets, PII masking before any LLM call, full audit log |

### 1.3 Non-Goals (v1)
- iOS app testing (planned v2).
- Replacing Jira/Azure DevOps — only link out to them (optional import in v2).
- Load/performance testing at scale (only basic response-time capture).
- Full penetration testing — security default scenarios are *checks*, not a pentest tool.

---

## 2. Users & Roles

| Role | Description | Key permissions |
|------|-------------|-----------------|
| **Admin** | QA Lead / tool owner | Everything a User can do, plus: manage test-case types, default test cases, templates, users, projects, report defaults (exit criteria, approvers), AI settings, execution settings (allowlists, limits), view audit log & usage |
| **User** | QA Engineer | Create projects/suites, upload user stories, generate test cases, edit suites, run tests (Web/API/Android), generate reports, download files. Sees only projects they own or are members of |
| **Viewer** (optional, v1.1) | PO / reviewer | Read-only access to suites, runs and reports shared with them |

Authentication: email + password with bcrypt/argon2 hashing, JWT access tokens (15 min) + refresh tokens (7 days, httpOnly cookie). Design the auth layer so Azure AD / Microsoft Entra SSO (OIDC) can be added later without schema changes (`users.auth_provider`, `users.external_id`).

First run: a CLI command `make seed-admin EMAIL=... PASSWORD=...` creates the first admin.

---

## 3. Template Analysis (the build agent MUST implement against this)

### 3.1 Test Cases Workbook — `QA_Test_Cases_Template.xlsx`

**Sheets:**
1. `Test Case` — the main sheet (header block + test case table).
2. One or more **evidence sheets** — in the sample: `Default Scenarios`, `Cash Hub`, `Cash Center`, `Service Center`. Each holds pasted screenshots (embedded images). Evidence sheets are named per evidence group (defaults always go to `Default Scenarios`; functional evidence groups are per feature/sub-area).

**Global styling (Test Case sheet):**
- Font: **Century Gothic, 9pt**, wrap text on all populated cells.
- Column widths: A≈23.5, B≈33.8, C≈53.2, D≈44.5, E≈45.8, F≈34.8, G≈16.2, H≈28.8, I≈9.2.

**Header block (rows 1–10):**

| Cell | Label (col A / D) | Value cell | Notes |
|------|-------------------|-----------|-------|
| A1 / B1 | Project Name | B1 | Label fill `#C00000` with white bold text; value fill `#F4735E`. Format in sample: `KUSALA: Branch Petty Cash Retirement Flow on Kusala` (`<APP IN CAPS>: <Feature/Project title>`) |
| A2 / B2 | User Group/Dept. | B2 | |
| A3 / B3 | Solution Provider | B3 | |
| A4 / B4 | Developers | B4 | Comma-separated names |
| A5 / B5 | Test Done By | B5 | |
| A6 / B6 | Test Reviewed By | B6 | |
| A7 / B7 | Testing Start Date | B7 | `DD/MM/YYYY` |
| A8 / B8 | Testing End Date | B8 | `DD/MM/YYYY` |
| A9 / B9 | Test Description | B9 | e.g. "This document seeks to outline the …" |
| D1 | RESULT ANALYSIS | — | Fill `#222A35`, text `#F2F2F2`, bold |
| D2 / E2 | No of Cases Tested | E2 | Value fill `#BDD6EE`, bold |
| D3 / E3 | No of Passes | E3 | |
| D4 / E4 | No of Failures | E4 | |
| D5 / E5 | Modification | E5 | |
| D6 / E6 | Not Tested | E6 | |
| D7 / E7 | Suspended | E7 | |
| D8 / E8 | Regression | E8 | |
| D10 / E10 | Endpoints/URL/Module Name | E10 | Test URL / module |

**Result Analysis values (E2:E8) must be written as live Excel formulas** so that when a tester edits a status manually in Excel, counts update. Example (range computed from the actual table extent):
- E2: `=COUNTA(A13:A70)-<banner row count>` or better `=COUNTIF(G13:G70,"?*")` (cases with any status)
- E3: `=COUNTIF(G13:G70,"Passed")`, E4: `"Failed"`, E5: `"Modification"`, E6: `"Not Tested"`, E7: `"Suspended"`
- E8 (Regression): `=COUNTIF(I13:I70,"Yes")` using a hidden/narrow helper column I, **or** COUNTIF on a "Regression" status — decide per Section 3.3.
Then run the LibreOffice recalculation step so cached values are present when opened in viewers that don't recalc.

**Test case table:**
- Row 11 = column headers (fill `#B4C6E7`, bold): `TESTCASE NO | FEATURE | OPERATIONS / SCENERIOS | STEPS TO EXECUTE | EXPECTED RESULT | ACTUAL RESULT | STATUS | EVIDENCE` (keep the team's spelling "SCENERIOS" exactly — it's the template).
- Row 12 = section banner `DEFAULT SCENARIOS`, merged **A12:H12**, bold.
- Default cases start at row 13.
- After the last default case, a section banner row `FUNCTIONAL SCENARIOS` (in sample: A44, bold — replicate the same merge/style as the default banner for consistency).
- Functional cases follow directly.
- **FEATURE column (B) is vertically merged** across consecutive rows sharing the same feature (e.g. B13:B17 "Login", B18:B19 "2FA", B45:B54 "Initiate Petty Cash Request"). Some templates also merge STEPS (D) when multiple cases share identical steps (e.g. D24:D26) — implement as optional: merge D only when consecutive steps text is identical *and* the feature is identical.
- **TESTCASE NO** format: `<Prefix>_<NNN>` zero-padded to 3 digits (e.g. `Kusala_001`). Numbering is **continuous** across default and functional sections. (Note: the sample has a duplicate `Kusala_031` at the section boundary — the tool must guarantee unique, gap-free IDs and warn on duplicates when importing.)
- **STEPS TO EXECUTE**: numbered lines separated by `\n` (`1. Launch the application.\n2. …`).
- **ACTUAL RESULT**: default text `As expected` when Passed; free text otherwise.
- **STATUS**: bold white text on a status colour fill. Sample Passed = `#00B050`. Define the full palette (admin-editable, Section 6.6):
  - Passed `#00B050`, Failed `#FF0000`, Not Tested `#A6A6A6`, Suspended `#FFC000`, Modification `#7030A0`, Blocked `#C55A11` (optional).
- **EVIDENCE**: an internal hyperlink to a cell on an evidence sheet. The displayed text is literally the link target, e.g. `Default Scenarios'!A1` (sample shows the display text starting with the sheet name and a trailing quote). Implement as a real internal hyperlink (`cell.hyperlink = Hyperlink(ref=..., location="'Default Scenarios'!A1")`) and display text `'<Sheet Name>'!A<n>` — the numbering `A1, A2, …` is the evidence index **within that evidence sheet**.

**Evidence sheets:**
- Default cases → `Default Scenarios` sheet. Functional cases → one evidence sheet per **evidence group** (defaults to the functional FEATURE name; user can override, e.g. by role/branch type as in the sample "Cash Hub / Cash Center / Service Center").
- Sheet names: max 31 chars, strip `[]:*?/\`, de-duplicate with suffix.
- For each case with evidence: write a caption in column A at the anchor row (`<TESTCASE NO> – <scenario short text>`), embed the screenshot(s) below it (scaled to max 900px width), and advance the anchor row by image height + 2 rows. The hyperlink in column H points to the caption cell.
- If a case has no evidence yet, EVIDENCE cell is left blank (not a broken link).

### 3.2 QA Test Completion Report — `QA_Test_Report_Template.docx`

Page layout: header line with "QA TEST COMPLETION REPORT"; footer contains a **text box with the classification label** ("Public" in the sample) — must be preserved. The document has embedded images (logos, checkbox glyphs) that must be preserved.

**Section-by-section field map:**

1. **Project info table (2 columns, red label cells `#C00000` style, grey value cells):**
   | Label | Field | Notes |
   |---|---|---|
   | Product Name | `product_name` | |
   | Pre-master PR Link | `pr_links[]` | One or more URLs, one per line, hyperlinked |
   | Version Number | `version_numbers[]` | One or more commit hashes / build numbers, one per line |
   | Test URL | `test_url` | Hyperlinked |
   | Workitem/ Repo URL | `workitem_url` | Hyperlinked |
   | Jira Link | `jira_link` | Hyperlinked |
   | General Description | `general_description` | Default: "Outlines the features of testing <Product Name> sent to the Quality Assurance team for testing." |

2. **(a) Certificate Summary** — line "Is this build certified for deployment? Yes ☐ No ☐" with one box ticked. Field: `certified: bool`. Auto-suggested (all executed cases passed AND zero open bugs) but the user must confirm.

3. **(b) BRD/SWR/ITR FEATURE STATUS IN THIS BUILD** — table: `S/N | Feature | Description | Implemented? (Yes ☐ No ☐) | Functional? (Yes ☐ No ☐)`. One row per **functional feature** in the suite. `Description` is AI-drafted ("To confirm that …") and editable. `Implemented?` defaults to Yes. `Functional?` defaults to Yes if all that feature's cases passed, else No. Row S/N numbered `1.`, `2.`, …

4. **(c) Exit Criteria** — table `S/N | Description`. Admin-managed default list (from template):
   1. All Test cases applicable were executed with screenshots attached
   2. All defects raised were resolved and confirmed as fixed
   3. Completion of User Acceptance Test with the Product owner and other Stakeholders
   User can add/remove per report.

5. **(d) Result Analysis** — two tables:
   - *Test Status Summary:* Test Cycles, Total Number of Test Cases, Passed, Failed, Un-executed (= Not Tested), Suspended, Modification-Requiring.
   - *Automation-to-Manual Tests Ratio* (e.g. `0:100`) — computed as % of cases whose latest execution was performed by QA Forge's automated runner vs manually marked, rounded to integers summing to 100.
   - *Bugs Summary:* Bugs Raised During Execution, Bugs Fixed and Retested, Opened Bugs.

6. **(e) EXCEPTIONS & OBSERVATIONS** — table `TestCase ID | Status Type | Description | SEVERITY | RISK ASSESSMENT`. One row per non-passed case or logged observation. If none: a single row with `N/A` in every column (as in the template).
   - Severity enum: Critical, High, Medium, Low. Risk assessment: free text (AI-drafted, editable).

7. **(f) Comments/Observation** — free text paragraphs. AI drafts from results + project context; user edits. Sample opening: "Functional testing for <Product Name> has been successfully completed, and thus is hereby certified ready for CAB review toward deployment." Admin can save reusable **note snippets** (e.g. the Kusala "configuration-driven workflow… security testing was not applicable" note) that users can insert with one click.

8. **(g) Reviews and Approvals** — table `Action | Name | Staff ID | Signature | Date`, rows: Tested By; Product Owner Concurrence; FT Lead, Quality Assurance; Head Quality Assurance (<Organisation>). Names/Staff IDs default from project settings; Signature left blank (v1) or an uploaded signature image (v1.1); Date `DD/MM/YYYY`.

**Template hygiene:** the sample contains a stray character ("s") after the comments section — the tokenised template should drop it.

### 3.3 Status vocabulary (single source of truth)
Test case `status` enum: `Passed`, `Failed`, `Not Tested`, `Suspended`, `Modification`, `Blocked`.
`is_regression: bool` flag on the case (counts into xlsx "Regression").
Mapping to report: Un-executed = Not Tested (+ Blocked), Modification-Requiring = Modification.

---

## 4. System Overview

```
┌─────────────────────────────── Web App (Next.js) ───────────────────────────────┐
│  Admin Console                      │  User Workspace                            │
│  - Test case types & defaults       │  - Projects & suites                       │
│  - Templates & mappings             │  - Generate test cases (story → cases)     │
│  - Report defaults, snippets        │  - Suite editor (grid)                     │
│  - Users, AI & execution settings   │  - Test Lab: Web / API / Android runs      │
│  - Audit log, usage                 │  - Reports (docx) & workbook (xlsx) export │
└──────────────────────────────────────┬───────────────────────────────────────────┘
                                       │ REST + SSE (live run progress)
┌──────────────────────────────── API (FastAPI) ──────────────────────────────────┐
│ Auth/RBAC │ CRUD │ Ingestion │ AI Orchestrator │ Doc Engine │ Run Orchestrator   │
└──────┬────────────┬──────────────┬─────────────────┬───────────────┬─────────────┘
       │            │              │                 │               │
  PostgreSQL     Redis        Object store       Anthropic API   Worker pool (queue)
                (queue,       (MinIO/S3:                          ├─ Web runner (Playwright)
                 cache,        uploads, APKs,                     ├─ API runner (httpx)
                 pub/sub)      evidence, exports)                 └─ Android runner (Appium +
                                                                      emulator container)
```

### 4.1 Tech stack (mandatory unless a strong reason is documented in `docs/decisions/`)
| Layer | Choice | Why |
|---|---|---|
| Frontend | Next.js 15 (App Router) + TypeScript, Tailwind, shadcn/ui, TanStack Query, TanStack Table (or AG Grid Community) for the suite grid, react-hook-form + zod | Fast to build, good data grids |
| Backend | Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 + Alembic | Python has the best libs for filling Office templates and for Playwright/Appium |
| Doc engine | `openpyxl` (xlsx), `docxtpl` + `python-docx` (docx), LibreOffice headless (formula recalc + PDF preview) | Preserves template styling |
| Queue / workers | Redis + `arq` (or Celery) | Long-running generation and test runs |
| DB | PostgreSQL 16 | |
| Storage | MinIO locally, S3-compatible in prod | |
| AI | Anthropic Messages API via official `anthropic` Python SDK, tool use + structured JSON output | |
| Web runner | Playwright (Python), Chromium headless | |
| API runner | `httpx`, `jsonschema`, `openapi-spec-validator`, `prance` (resolve $refs) | |
| Android runner | Appium 2 + UiAutomator2 driver, Android emulator in Docker (e.g. `budtmo/docker-android` or similar), `apkanalyzer`/`aapt2`, `bundletool` for AAB | |
| Packaging | Docker Compose (dev + single-server prod), Makefile | |
| Testing the tool | pytest, Playwright (E2E of the UI), Vitest for frontend units | |

### 4.2 Repo structure
```
qa-forge/
├─ CLAUDE.md
├─ docs/PRD.md, docs/decisions/*.md
├─ docker-compose.yml, Makefile, .env.example
├─ templates/
│  ├─ source/                 # original team templates (read-only)
│  └─ tokenized/              # generated working templates (docx with Jinja tags, xlsx mapping json)
├─ apps/web/                  # Next.js
│  └─ src/app/(auth)|(admin)|(workspace)/...
├─ services/api/
│  ├─ app/main.py
│  ├─ app/core/ (config, security, rbac, logging)
│  ├─ app/models/ app/schemas/ app/routers/
│  ├─ app/services/
│  │  ├─ ingestion/          # docx/pdf/txt/md → text; spec parsing
│  │  ├─ ai/                 # prompts/, client.py, schemas.py, masking.py
│  │  ├─ docengine/          # xlsx_writer.py, docx_writer.py, template_registry.py
│  │  └─ runs/               # orchestrator.py, web/, api/, android/
│  ├─ app/workers/
│  └─ tests/ (unit, integration, golden/)
└─ infra/ (android-emulator/, playwright/, minio/)
```

---

## 5. Data Model (PostgreSQL)

All tables: `id UUID PK`, `created_at`, `updated_at`, `created_by` where sensible. Soft delete via `deleted_at` on user-facing entities.

```
users(id, email UNIQUE, full_name, staff_id, role ENUM(admin,user,viewer), password_hash,
      auth_provider DEFAULT 'local', external_id, is_active, last_login_at)

test_case_types(id, name UNIQUE, description, id_prefix_hint, sort_order, is_active)
   -- e.g. "Web Application", "Mobile Application (Android)", "API / Microservice",
   --      "Workflow Configuration (Kusala)", "Back-office Portal"

default_test_cases(id, type_id FK, feature, scenario, steps, expected_result,
                   default_actual_result DEFAULT 'As expected', sort_order,
                   evidence_group DEFAULT 'Default Scenarios', tags TEXT[],
                   is_active, version INT)
   -- versioned: editing creates new version; suites snapshot the version they used

templates(id, kind ENUM(xlsx_test_cases, docx_report), name, version, file_key,
          mapping_json JSONB, is_default, type_id FK NULL, status ENUM(draft,active,archived),
          uploaded_by, notes)
   -- type_id NULL = applies to all types; a type-specific template overrides the default

report_defaults(id, exit_criteria JSONB[], approval_roles JSONB[], classification_label,
                organisation_name)

note_snippets(id, title, body, tags TEXT[], is_active)

projects(id, name, app_code, id_prefix, user_group_dept, solution_provider, developers TEXT[],
         reviewed_by, default_test_url, members UUID[], approvers JSONB)
   -- id_prefix e.g. "Kusala"

user_stories(id, project_id, title, source ENUM(upload,paste,url), file_key, raw_text,
             extracted_text, acceptance_criteria JSONB, uploaded_by)

test_suites(id, project_id, type_id, name, status ENUM(draft,in_review,final),
            story_ids UUID[], header_json JSONB, default_version_snapshot JSONB,
            template_xlsx_id, template_docx_id, test_cycle INT DEFAULT 1)
   -- header_json: project name line, dept, provider, devs, done by, reviewed by,
   --              start/end dates, description, endpoint/URL

test_cases(id, suite_id, section ENUM(default,functional), case_no INT, display_id,
           feature, scenario, steps, expected_result, actual_result, status, is_regression,
           evidence_group, priority ENUM(P1..P4), technique TEXT[], traceability JSONB,
           source ENUM(default,ai,manual,run), default_case_id NULL, included BOOL DEFAULT true,
           execution_mode ENUM(manual,automated) NULL, last_run_id NULL, sort_order)

evidence(id, test_case_id, run_id NULL, kind ENUM(screenshot,request_log,video,file),
         file_key, caption, sort_order)

generation_jobs(id, suite_id, story_ids, status, model, prompt_version, input_tokens,
                output_tokens, cost_estimate, error, started_at, finished_at)

test_runs(id, suite_id NULL, project_id, target ENUM(web,api,android), status
          ENUM(queued,running,passed,failed,error,cancelled), config_json JSONB (secrets
          referenced by id only), guidance_text, selected_case_ids UUID[], worker_id,
          started_at, finished_at, summary_json)

run_steps(id, run_id, test_case_id NULL, seq, action, target, input_masked, assertion,
          outcome ENUM(pass,fail,skip,error), message, screenshot_evidence_id, duration_ms)

secrets(id, owner_id, project_id, name, ciphertext, kind ENUM(password,token,api_key,
        oauth_client), created_at)   -- never returned in plaintext to the client

bugs(id, suite_id, test_case_id, title, description, severity, status
     ENUM(open,fixed,retested,closed), external_link)

reports(id, suite_id, template_docx_id, fields_json JSONB, file_key, version, generated_by)

audit_log(id, actor_id, action, entity, entity_id, diff JSONB, ip, at)
app_settings(key PK, value JSONB)     -- AI model config, limits, allowlists, status palette
```

---

## 6. Admin End — Functional Requirements

### 6.1 Test Case Types
- **ADM-TT-1** CRUD test case types: name, description, sort order, active toggle.
- **ADM-TT-2** Deactivated types disappear from user dropdowns but existing suites keep working.
- **ADM-TT-3** Duplicate a type (copies all its default cases) — useful for e.g. "Web Application" → "Web Application (Internal, AD login)".

### 6.2 Default Test Cases (per type)
- **ADM-DC-1** Grid editor per type with columns: Feature, Operations/Scenario, Steps to Execute (multiline), Expected Result, Default Actual Result, Evidence Group, Tags, Active.
- **ADM-DC-2** Drag-and-drop reorder; order is preserved in generated workbooks. Rows with the same Feature must stay contiguous (UI groups them; warn if split).
- **ADM-DC-3** Bulk import from an existing team workbook: upload an `.xlsx` in template format → parser reads rows between the `DEFAULT SCENARIOS` and `FUNCTIONAL SCENARIOS` banners, un-merges FEATURE cells (propagates the feature name down merged ranges), and previews before saving. **Seed data:** on first run, import the 31 default scenarios from `templates/source/QA_Test_Cases_Template.xlsx` into a type called "Web Application" (Login ×5, 2FA ×2, Logout, Session Timeout ×3, Exception Logging ×3, Audit Trail ×3, Encryption, Usability ×9, Injection, Broken Authentication, Security Misconfiguration, Broken Access Control).
- **ADM-DC-4** Bulk export to CSV/xlsx.
- **ADM-DC-5** Placeholders allowed in default text and resolved at generation time: `{{app_name}}`, `{{login_identifier}}` (email/username/phone), `{{session_timeout_minutes}}`, `{{2fa_method}}` (e.g. OneToken/OTP), `{{test_url}}`. Users are prompted for any unresolved placeholder values when selecting the type.
- **ADM-DC-6** Versioning: each save bumps `version`; suites snapshot the defaults at creation time so later admin edits don't silently change existing suites. User can click "Refresh defaults" on a draft suite to pull the latest.
- **ADM-DC-7** Optional per-case "Automatable hint" field (free text or a small DSL, e.g. `login_valid`, `session_timeout:5m`) so the Web runner can execute common defaults deterministically.

### 6.3 Template Management
- **ADM-TM-1** Upload `.xlsx` test-case templates and `.docx` report templates. Keep versions; mark one of each as **default**; optionally assign a template to a specific test-case type.
- **ADM-TM-2** **Template onboarding wizard:**
  - *XLSX:* the system auto-detects header labels (Project Name, RESULT ANALYSIS, …), the table header row, banner rows and column letters, then shows a mapping form pre-filled (JSON stored in `templates.mapping_json`, schema in Appendix B). Admin confirms/adjusts. The system captures **style samples** (label/value fills, header fill, banner style, body style, status palette) from the template cells.
  - *DOCX:* the system produces a **tokenised copy** (docxtpl Jinja tags inserted in the value cells and loops over table rows). Provide an automated tokeniser for the known template (Appendix C token list) plus a manual path: admin downloads the tokenised file, adjusts tags in Word, re-uploads. Validate that all required tokens exist.
- **ADM-TM-3** **Preview:** render a sample output (from built-in fixture data) to PDF via LibreOffice and show it in-browser before activating.
- **ADM-TM-4** A template cannot be activated if the preview render fails or required mappings/tokens are missing.

### 6.4 Report Defaults
- **ADM-RD-1** Manage default Exit Criteria list (seeded with the three from the template).
- **ADM-RD-2** Manage approval roles (seeded: Tested By; Product Owner Concurrence; FT Lead, Quality Assurance; Head Quality Assurance (Sterling Bank)) — organisation name editable.
- **ADM-RD-3** Classification label for footer (Public / Internal / Confidential).
- **ADM-RD-4** Note snippets library (title, body, tags).

### 6.5 Users & Projects
- **ADM-UP-1** Invite/create users, set role, deactivate, reset password.
- **ADM-UP-2** Admin sees all projects; can reassign ownership.

### 6.6 AI & Execution Settings
- **ADM-AI-1** Anthropic API key (stored encrypted; masked in UI), model per task (generation, report drafting, test execution agent) — defaults: generation & drafting `claude-sonnet-5-5`, execution agent `claude-sonnet-5-5` with optional `claude-opus-5-5` for hard flows, light tasks (classification, title drafting) `claude-haiku-4-5-20251001`. Model names must be config values, never hard-coded in logic.
- **ADM-AI-2** Team **style guide** text injected into every generation prompt (e.g. "Scenarios start with 'Check that…'", "Use NGN amounts with comma separators", "Include boundary value cases for every limit").
- **ADM-AI-3** **Few-shot examples library:** admin marks past approved suites (or rows) as exemplars. Seed with the Petty Cash functional scenarios from the template.
- **ADM-AI-4** Monthly token budget + per-user daily cap; usage dashboard (tokens, cost estimate, by user/project).
- **ADM-EX-1** Web/API target **allowlist** (domains, IP ranges, e.g. `*.apps.non-core-dev.sterlingbank.com`). Runs against non-allowlisted hosts are blocked (SSRF protection). A "production environment" flag per host forces read-only mode (no form submissions) unless admin overrides.
- **ADM-EX-2** Limits: max steps per case, max run duration, max concurrent runs, max APK size (default 300 MB).
- **ADM-EX-3** Status palette editor (status → fill hex, font colour).

### 6.7 Audit & Monitoring
- **ADM-AU-1** Audit log of every create/update/delete, generation, run, download, login. Filter + CSV export.

---

## 7. User End — Functional Requirements

### 7.1 Navigation
Left sidebar: **Dashboard · Projects · Generate Test Cases · Test Suites · Test Lab · Reports · Settings (profile)**.
Dashboard: recent suites, runs in progress, pass-rate chart per suite, quick actions.

### 7.2 Projects
- **USR-PR-1** Create project: Name, App Code (e.g. KUSALA), Test Case ID Prefix (e.g. `Kusala`), User Group/Dept, Solution Provider, Developers (tags), Reviewed By, default Test URL, approvers (name + staff ID per approval role), members.
- **USR-PR-2** These values pre-fill the workbook header and report fields.

### 7.3 Generate Test Cases (core flow)
**Screen layout (single page, top → bottom):**

1. **Setup panel**
   - Project (dropdown) · Suite name · **Test Case Type (dropdown — from admin types)** · Test cycle (default 1).
   - Header fields (pre-filled from project, editable): Project Name line (auto `APPCODE: Suite name`), User Group/Dept, Solution Provider, Developers, Test Done By (current user), Test Reviewed By, Testing Start/End Date, Test Description (AI can draft), Endpoints/URL/Module Name.
   - Placeholder values required by the selected type's defaults (ADM-DC-5).

2. **Default Scenarios section** — appears **immediately when a type is selected** (before any AI call):
   - Read-only-by-default grid of that type's active default cases, grouped by Feature, in admin order.
   - Per-row **Include** checkbox (e.g. untick Encryption if not applicable), and "Edit for this suite" (edits apply only to this suite, row marked "modified from default").
   - IDs preview live (`Prefix_001…`).

3. **User Story input**
   - Upload one or more files: `.docx`, `.pdf`, `.txt`, `.md`, `.xlsx`/`.csv` (story tables), images of BRD pages (OCR via Claude vision). Or paste text. Max 20 MB per file.
   - Optional: "Additional context" textarea (business rules, roles, limits, out-of-scope), and "Focus areas" chips (Boundary values, Negative tests, Role/permission, Workflow routing, Validation, Search/filter, Notifications, Audit, Integration).
   - Coverage depth selector: **Essential / Standard / Exhaustive** (roughly 10–20 / 20–40 / 40–80 cases per story).
   - Button **Generate Functional Test Cases**.

4. **Functional Scenarios section** — appears **below the defaults** once generated:
   - Streamed in progressively (feature by feature) with a progress indicator.
   - Same grid columns as the workbook: TESTCASE NO · FEATURE · OPERATIONS / SCENARIOS · STEPS TO EXECUTE · EXPECTED RESULT · ACTUAL RESULT · STATUS · EVIDENCE, plus tool-only columns: Priority, Technique (BVA, EP, Negative, State transition, Role-based, …), Traces to (acceptance criterion ID), Evidence group, Regression flag.
   - Row actions: edit inline, duplicate, delete, move, **regenerate this row**, **"generate more like this"**, add manual row.
   - Feature actions: rename feature, **regenerate feature**, **add more cases for feature** (with a hint box).
   - **Coverage panel:** list of extracted acceptance criteria / business rules with the number of cases tracing to each; criteria with zero cases are highlighted red with a "Generate cases for this" button.
   - **Duplicate check:** functional cases that semantically duplicate a default case (e.g. another "valid login" case) are flagged and hidden by default.

5. **Actions bar:** Save draft · Download **Test Cases (.xlsx)** · Send to Test Lab · Generate Report.

**Acceptance criteria (USR-GEN):**
- **USR-GEN-1** Selecting a type shows its defaults within 500 ms without calling the AI.
- **USR-GEN-2** Functional cases appear below defaults; IDs continue sequentially from the last included default.
- **USR-GEN-3** Changing Include on a default renumbers all subsequent IDs.
- **USR-GEN-4** Every AI-generated case has non-empty Feature, Scenario, Steps (numbered), Expected Result; Actual Result blank and Status `Not Tested` until executed or set.
- **USR-GEN-5** For every numeric limit found in the story, at least one "equal to limit" and one "limit + 1 unit" case exists (the sample's 150,000 vs 150,001 pattern). Validated in post-processing; missing ones auto-requested from the model.
- **USR-GEN-6** For every approval chain / routing rule found, cases exist for each hop and for enforcement regardless of amount/condition.
- **USR-GEN-7** Downloaded xlsx matches template (Section 3.1, 13.4).

### 7.4 Test Suites (editor)
- List of suites with status, type, counts per status, last run, last report.
- Suite editor = the same grid, plus **execution columns** editable manually: Actual Result, Status (dropdown with colours), Regression flag, Evidence upload (drag-and-drop screenshots per case, paste from clipboard with Ctrl+V), Bug link.
- Bulk actions: set status for selected rows ("Mark all as Passed / As expected"), assign evidence group, export selection.
- Test cycles: "Start new cycle" clones statuses to history and resets to Not Tested (keeps history for report "Test Cycles" count).
- Import: upload an existing team workbook to create a suite (reverse of export — parse both sections, statuses, and evidence images from evidence sheets using the H-column hyperlinks).

### 7.5 Reports
- **USR-RP-1** From a suite, click **Generate Report** → report form pre-filled:
  - Project info (Product Name, PR links, version numbers, test URL, workitem URL, Jira link, general description).
  - Certificate: Yes/No (suggested value shown with reason).
  - Feature status table (auto from functional features; editable description/Implemented/Functional).
  - Exit criteria (defaults, editable).
  - Result Analysis — auto-computed, read-only numbers (with an "override" toggle requiring a reason, logged to audit).
  - Automation-to-manual ratio — auto.
  - Bugs summary — auto from `bugs` table (or manual entry).
  - Exceptions & observations — auto rows for non-passed cases; AI drafts description/severity/risk; editable; `N/A` row if empty.
  - Comments/Observation — AI draft + insert snippet.
  - Reviews & approvals — from project approvers; dates editable.
- **USR-RP-2** Buttons: **Preview (PDF)** · **Download .docx** · Download .pdf (optional) · Save version.
- **USR-RP-3** Numbers in the report must equal the xlsx Result Analysis for the same suite and cycle (automated consistency check before download; block with error if mismatch).
- **USR-RP-4** Report versions kept; regenerate after more runs.

### 7.6 Test Lab — AI Test Execution
A single "New Test Run" page with a **Target selector: Web · API · Android**. Every run:
- Can be attached to a suite (results write back into the suite's cases) or standalone ("exploratory run" → can later "Save as suite").
- Accepts **guidance** in any combination of: free-text description of what to test, pasted/uploaded user story, or selected test cases from a suite (checkbox list).
- Shows a **live run view** (SSE): current case, step log, latest screenshot, pass/fail counters, Stop button.
- Produces per-case: Status, Actual Result (AI-written, factual), step log, evidence (screenshots / request-response logs), and flags "needs human review" when the AI is uncertain.
- Nothing is written into the suite until the user reviews the run and clicks **Apply results** (per case or all) — protects against AI mistakes.

#### 7.6.1 Web
**Inputs:** URL (must match allowlist) · Environment label (QA/UAT/Prod — Prod forces read-only unless admin override) · Credentials: pick saved secret(s) or enter new (saved encrypted, referenced by name) · 2FA handling: *none / static test token / manual* (manual = run pauses and the user types the OTP/OneToken into the live view) · Viewports: Desktop 1366×768 (default), Mobile 390×844, Tablet 768×1024 · Guidance (description / story / selected cases) · Max steps per case · Record video (on/off).

**Execution model (hybrid, implement both):**
- **Agent mode (default):** for each test case, an execution agent (Claude with tool use) drives Playwright through a constrained tool set: `navigate(url)`, `snapshot()` (accessibility tree + visible text, trimmed), `screenshot()`, `click(ref)`, `fill(ref, value | secret_ref)`, `select(ref, option)`, `press(key)`, `wait_for(text|ref, timeout)`, `assert_visible(text|ref)`, `assert_url(pattern)`, `back()`, `go_idle(minutes)` (for session-timeout defaults — simulated by clearing/advancing where possible, else real wait with a cap), `finish(status, actual_result, confidence)`. Secrets are passed to the browser by reference (`secret_ref`) — the LLM never sees their plaintext.
- **Script mode:** after a passing agent run, the recorded action trace is converted into a deterministic Playwright script stored with the case (`automation_script`). Subsequent runs (regression) replay the script without the LLM; on failure, optionally fall back to agent mode ("self-heal") and flag.
- **Deterministic defaults:** default cases with an Automatable hint (ADM-DC-7) use built-in routines (login valid/invalid, blank fields, logout + back button, session timeout, security headers check, basic SQLi payload check in inputs, responsive rendering at 3 viewports with screenshots).

**Evidence:** screenshot after every assertion and at `finish`; full-page screenshot on failure; optional video; console errors and failed network requests captured into the step log.

#### 7.6.2 API
**Inputs:** Base URL (allowlist) · Spec source: OpenAPI/Swagger (file or URL), Postman collection v2.1, or pasted cURL commands, or none (describe endpoints in text) · Auth: None / Bearer / API key (header or query) / Basic / OAuth2 client credentials (token URL + client id/secret secret refs) · Default headers · Guidance (description / story / selected cases) · Environment variables (key-value, secrets allowed).

**Flow:**
1. Parse spec → endpoint catalogue shown to user (select endpoints in scope).
2. AI generates API test cases (if not provided) in the same suite format: Feature = endpoint/resource, Scenario = "Check that POST /transfers with amount above limit returns 400 …", Steps = request details, Expected = status code + key assertions. Categories: happy path, required field missing, invalid types/formats, boundary values, auth missing/invalid/expired, permission (other user's resource — IDOR), idempotency (duplicate reference), pagination/filtering, schema conformance, error message format, response time threshold.
3. Each case compiled into an executable request plan (JSON: method, path, headers, body, extract variables for chaining, assertions: status, JSON path equals/contains/matches, schema valid, header present, latency < N ms).
4. Runner executes with httpx (timeouts, retries off by default), supports chained flows (create → get → update → delete) via extracted variables.
5. Evidence = masked request/response log (headers + body, truncated to 50 KB) rendered as an image for the xlsx evidence sheet (monospace render to PNG) **and** stored as text.
6. Exports: Postman collection and a pytest file of the executed plan.

#### 7.6.3 Android
**Inputs:** Upload `.apk` (or `.aab` → converted to universal APK with bundletool; requires signing config or debug keystore) · Auto-detected package name, launch activity, version (via aapt2/apkanalyzer), shown for confirmation · Device profile (Pixel-class, API 33/34 default) · Credentials / test data (secret refs) · OTP handling (manual pause, like Web) · Guidance (description / story / selected cases) · Permissions: auto-grant on install (toggle).

**Flow:** queue job → start (or reuse warm) emulator container → install APK → Appium UiAutomator2 session → execution agent with tools: `snapshot()` (UI hierarchy XML trimmed to interactive nodes), `screenshot()`, `tap(ref)`, `type(ref, value|secret_ref)`, `swipe(dir)`, `scroll_to(text)`, `back()`, `home()`, `launch_app()`, `background_app(seconds)` (session timeout), `rotate(orientation)`, `wait_for(text)`, `assert_visible(text)`, `finish(...)`. Capture logcat crashes/ANRs into the run log and auto-fail the case on crash. Uninstall and wipe emulator data after run.
**Constraints:** host must support KVM for the emulator; document fallback to a cloud device farm (BrowserStack/Sauce Labs/LambdaTest via Appium remote URL) as a configurable runner backend — interface `AndroidDeviceProvider` with `LocalEmulatorProvider` implemented in v1, `RemoteAppiumProvider` stubbed.

#### 7.6.4 Run result → suite & documents
- Applying results sets `status`, `actual_result`, `execution_mode=automated`, attaches evidence with `evidence_group` → these drive xlsx evidence sheets and hyperlinks, and the report's automation ratio.
- Failed cases can create a draft **bug** (title, steps to reproduce from step log, expected vs actual, screenshots) → counts toward report Bugs Summary; export to Jira/Azure DevOps via copy-ready text (API integration v2).

---

## 8. AI Design

### 8.1 Principles
- All AI outputs are **structured JSON validated against Pydantic schemas**; invalid output → one automatic repair retry with the validation errors → otherwise surface error.
- Prompts are versioned files in `app/services/ai/prompts/` (`generate_functional_cases.v1.md`, etc.); `prompt_version` stored on each job.
- **PII/secret masking** (`masking.py`) runs on all text before sending: account numbers (10-digit NUBAN), BVN/NIN (11-digit), card PANs (Luhn), emails and phone numbers (configurable: mask or keep), passwords/tokens found in text, anything in `secrets`. Masked tokens are reversible only server-side where needed.
- Temperature low (0–0.3) for generation; model/effort configurable.
- Log token usage per call into `generation_jobs` / run summary.

### 8.2 Functional test-case generation pipeline
1. **Extract** text from uploads (python-docx, pdfplumber, openpyxl; images → Claude vision transcription).
2. **Analyse** (call 1): produce `StoryAnalysis` JSON — features, actors/roles, acceptance criteria (with IDs AC-1…), business rules, numeric limits (value, unit, applies_to), state/status list, approval chains, integrations, validations, out-of-scope, ambiguities/questions.
   - Show ambiguities to the user as "Questions the AI has" (non-blocking; answering them and regenerating improves output).
3. **Generate** (call 2, per feature, parallel with concurrency limit): `FunctionalCase[]` using analysis + team style guide + few-shot exemplars + the list of default scenarios (to avoid duplicates) + coverage depth + focus areas.
4. **Post-process:** normalise wording (scenario starts with "Check that…" unless style guide says otherwise), number the steps, BVA completeness check (USR-GEN-5), routing completeness (USR-GEN-6), semantic de-dup (embedding or simple normalised-text similarity > 0.9) against defaults and within the set, traceability check (every case traces to ≥1 AC; every AC has ≥1 case) → targeted top-up call for gaps.
5. **Order:** features in story order; within a feature: happy path → boundaries → negative → permissions → routing/state → misc.

JSON schema for a generated case (see Appendix A for full schemas):
```json
{
  "feature": "Initiate Petty Cash Request",
  "scenario": "Check that a Cash Centre initiator cannot submit a request above the 50K limit",
  "steps": ["Log in as Cash Centre initiator.", "Enter request amount = 50,001.", "Submit."],
  "expected_result": "System blocks submission and displays a limit-exceeded validation error.",
  "priority": "P1",
  "techniques": ["boundary_value", "negative"],
  "traces_to": ["AC-3"],
  "evidence_group": "Cash Center",
  "test_data": {"amount": "50,001", "role": "Cash Centre initiator"}
}
```

### 8.3 Report drafting
One call with: suite metadata, per-feature pass/fail counts, non-passed cases with actual results, bugs, run notes → returns `feature_descriptions[]`, `exceptions[]` (id, status type, description, severity, risk), `comments` (paragraphs). Tone: formal, concise, matches the sample report. User always reviews before download.

### 8.4 Execution agent
- System prompt defines role (careful QA tester), the tool set, rules: only interact with the allowlisted host; never guess credentials; use `secret_ref`; take a screenshot before `finish`; decide pass/fail strictly against the Expected Result; if the expected result cannot be verified, return `Blocked` with reason; confidence 0–1; stop after max steps.
- Context management: send only the latest snapshot (trimmed to interactive elements, max ~8k tokens) + a compact history of prior actions; screenshots sent as images only when snapshot is insufficient (config).
- Per-case isolation: fresh browser context / app relaunch per case unless the case declares a dependency (`depends_on`).

---

## 9. Document Engine Requirements

### 9.1 XLSX writer (`docengine/xlsx_writer.py`)
- Load the active template with openpyxl (**do not** create a new workbook). Clear sample data rows below the header row, remove sample evidence sheets, keep sheet order `Test Case` first.
- Write header block per mapping. Write Result Analysis formulas.
- Write banner `DEFAULT SCENARIOS`, default rows, banner `FUNCTIONAL SCENARIOS`, functional rows — copying cell styles from captured style samples (font, fill, border, alignment, wrap).
- Merge FEATURE cells for contiguous same-feature runs within each section (never across the banner).
- Status cell fill/font from palette.
- Create evidence sheets, embed images (Pillow resize, keep aspect), write captions, create internal hyperlinks in H.
- Set row heights to fit wrapped text (estimate: lines × 12pt, min 15pt) so text isn't clipped.
- Run LibreOffice recalc (headless) so formula values are cached; verify zero formula errors.
- File name: `<AppCode>_<Suite name>_QA_Test_Cases_<YYYYMMDD>.xlsx`.

### 9.2 DOCX writer (`docengine/docx_writer.py`)
- Render tokenised template with docxtpl; loops for PR links, version numbers, feature rows, exit criteria rows, exceptions rows, approval rows.
- Checkboxes: render `☒` / `☐` (MS Gothic / Segoe UI Symbol) via conditional tags, or swap the checkbox images if the tokeniser keeps the template's image-based boxes — pick one approach in the tokeniser and document it.
- Hyperlinks for URL fields (use docxtpl `RichText` with `url_id`).
- Preserve header, footer text box (classification label bound to `{{ classification_label }}`), images, styles.
- Optional PDF export via LibreOffice.
- File name: `<Product Name>_QA_Test_Report_<YYYYMMDD>.docx`.

### 9.3 Round-trip importers
- `xlsx_importer.py`: template-format workbook → suite (handles merged features, banners, statuses, hyperlinks → evidence images by anchor).
- Used for ADM-DC-3 and USR suite import.

---

## 10. API Surface (FastAPI, prefix `/api/v1`)

Auth: `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /me`.

Admin (role=admin):
- `GET|POST /admin/types`, `GET|PATCH|DELETE /admin/types/{id}`, `POST /admin/types/{id}/duplicate`
- `GET|POST /admin/types/{id}/defaults`, `PATCH|DELETE /admin/defaults/{id}`, `POST /admin/types/{id}/defaults/reorder`, `POST /admin/types/{id}/defaults/import` (multipart xlsx → preview), `POST .../import/confirm`, `GET /admin/types/{id}/defaults/export`
- `GET|POST /admin/templates`, `POST /admin/templates/{id}/detect-mapping`, `PUT /admin/templates/{id}/mapping`, `POST /admin/templates/{id}/tokenize`, `POST /admin/templates/{id}/preview`, `POST /admin/templates/{id}/activate`
- `GET|PUT /admin/report-defaults`, `CRUD /admin/snippets`, `CRUD /admin/users`, `GET|PUT /admin/settings/{key}`, `GET /admin/audit`, `GET /admin/usage`, `CRUD /admin/exemplars`

User:
- `CRUD /projects`, `GET /types` (active only), `GET /types/{id}/defaults` (active, resolved placeholders)
- `POST /stories` (multipart or text), `GET /stories/{id}`
- `CRUD /suites`, `POST /suites/{id}/refresh-defaults`
- `POST /suites/{id}/generate` → job id; `GET /jobs/{id}`; `GET /jobs/{id}/events` (SSE stream of cases)
- `POST /suites/{id}/cases`, `PATCH /cases/{id}`, `DELETE /cases/{id}`, `POST /suites/{id}/cases/bulk`, `POST /cases/{id}/regenerate`, `POST /suites/{id}/features/{name}/regenerate|more`
- `POST /cases/{id}/evidence` (multipart), `DELETE /evidence/{id}`
- `POST /suites/{id}/export/xlsx` → file; `POST /suites/import` (xlsx)
- `POST /suites/{id}/cycles`
- `CRUD /bugs`
- `POST /suites/{id}/reports/draft` (AI drafts), `PUT /reports/{id}`, `POST /reports/{id}/render?format=docx|pdf`
- `CRUD /secrets` (write-only values)
- `POST /runs` (target + config), `GET /runs/{id}`, `GET /runs/{id}/events` (SSE), `POST /runs/{id}/cancel`, `POST /runs/{id}/input` (manual OTP), `POST /runs/{id}/apply`
- `POST /api-specs/parse` (OpenAPI/Postman/cURL → endpoint catalogue)
- `POST /apks` (multipart, chunked upload) → metadata

All list endpoints: pagination (`limit`, `cursor`), filtering, sorting. Errors: RFC 7807 problem+json.

---

## 11. UI Screens (checklist for the build agent)

Auth: Login · Forgot/Reset password.
Admin: Admin dashboard · Types list · Type detail with Defaults grid (+ import wizard) · Templates list · Template onboarding wizard (mapping form / tokenise / preview) · Report defaults · Snippets · Users · AI settings · Execution settings · Status palette · Exemplars · Audit log · Usage.
User: Dashboard · Projects list/detail · Generate Test Cases (Section 7.3 single page) · Suites list · Suite editor · Report builder + preview · Test Lab: New Run (Web/API/Android tabs) · Live run view · Run results review (apply per case) · Runs history · Bugs list · Secrets (per project) · Profile.

UX requirements: responsive down to 1280 px (desktop-first), keyboard-friendly grid (Tab/Enter to edit, Ctrl+V to paste screenshots as evidence), autosave drafts every 5 s, optimistic updates, toast notifications, empty states with guidance, dark/light theme, colour of status chips identical to workbook palette.

---

## 12. Non-Functional Requirements

| Area | Requirement |
|---|---|
| Performance | Defaults render < 500 ms; generation for a 3-page story < 3 min (Standard depth); xlsx export < 10 s for 300 cases + 100 screenshots; docx render < 5 s |
| Scalability | 20 concurrent users; 3 concurrent web runs, 1–2 concurrent Android runs per host (configurable) |
| Security | OWASP ASVS L2 basics: argon2 hashing, JWT rotation, CSRF protection for cookie flows, rate-limited login (5/min), RBAC checks on every endpoint (ownership, not just auth), secrets encrypted with AES-GCM/Fernet using a key from env/KMS, no secrets in logs, SSRF allowlist, upload type sniffing + size limits, APKs executed only inside the emulator container, containers run as non-root, dependency scanning in CI |
| Privacy | PII masking before LLM calls; configurable retention (default: uploads & evidence 180 days, audit log 2 years); "delete project" purges storage objects |
| Reliability | Jobs are idempotent and resumable; worker crash → job marked error with retry button; all runs have hard timeouts |
| Observability | Structured JSON logs, request IDs, `/health` & `/ready`, basic Prometheus metrics (jobs, run durations, token usage) |
| Accessibility | WCAG 2.1 AA for the web UI (labels, focus states, contrast) |
| Portability | `docker compose up` brings up everything locally; Android runner optional profile (`--profile android`) |

---

## 13. Testing Strategy for QA Forge itself

13.1 **Unit tests** (pytest): masking, ID numbering/renumbering, feature-merge range calculation, status counting, placeholder resolution, spec parsers, BVA completeness checker, sheet-name sanitiser.
13.2 **Integration tests:** API endpoints with a test Postgres (testcontainers), RBAC matrix tests (every admin endpoint returns 403 for user role; users can't read other users' projects).
13.3 **AI tests:** a `FakeLLM` returning fixture JSON so the pipeline is tested offline; a small opt-in `-m live_llm` suite using the Petty Cash story fixture asserting structural properties (limits 150K/50K → BVA cases present; SSA → FINOPS Officer → FINOPS Verifier chain covered).
13.4 **Golden-file tests for documents:**
- Generate xlsx from fixture suite → assert: sheet names, header labels & positions, fills (`C00000`, `F4735E`, `222A35`, `BDD6EE`, `B4C6E7`, status colours), font Century Gothic 9, column widths ±0.5, banner merges, feature merges, formulas in E2:E8 evaluate to expected counts after recalc, hyperlinks resolve to existing cells, images present on evidence sheets.
- Generate docx → assert all tokens replaced (no `{{`/`{%` left), table row counts, checkbox states, footer label, hyperlinks; render to PDF and compare page images against a stored baseline with a tolerance (visual regression).
- Round trip: import the original team xlsx → export → re-import → same data.
13.5 **E2E (Playwright on the UI):** admin creates type + defaults → user selects type → defaults appear → uploads story (FakeLLM) → functional cases appear below → downloads xlsx → generates report.
13.6 **Runner tests:** local demo web app (tiny FastAPI+HTML login/limit form) in `infra/demo-target/` used by the Web runner tests; a mock API (Prism from an OpenAPI file) for API runner tests; Android runner smoke test against a sample open-source APK (skipped when no KVM).

---

## 14. Seed & Fixture Data
- Type "Web Application" with the 31 default scenarios from the team template (imported via ADM-DC-3 logic at seed time).
- Types "API / Microservice" and "Mobile Application (Android)" with sensible starter defaults (admin will refine): API — auth required, invalid token, expired token, rate limiting, HTTPS only, security headers, error format, sensitive data not in responses/logs, input validation/injection, IDOR; Android — install/launch, login valid/invalid, biometric/PIN (if applicable), session timeout on background, logout, app permissions, orientation, offline handling, screenshots blocked on sensitive screens (FLAG_SECURE), root detection, data not stored in plaintext.
- Project "Kusala" (prefix `Kusala`) with a fixture story "Branch Petty Cash Retirement Flow" (write a short synthetic story reproducing the rules visible in the template: Service Center & Cash Hub limit 150,000, Cash Centre 50,000 independent of parent branch, routing to SSA, disbursed requests to initiator task list, retire/close, search by Request ID/date/amount, retirement form fields, approval chain SSA → FINOPS Officer → FINOPS Verifier, final approval debits account).
- Exemplars: the 26 functional scenarios from the template.
- Report defaults: 3 exit criteria, 4 approval roles, label "Public".

---

## 15. Risks & Mitigations
| Risk | Mitigation |
|---|---|
| AI generates plausible but wrong cases | Mandatory human review UI, traceability & coverage panel, style guide + exemplars, "needs review" flags |
| AI marks a failing test as passed | Strict expected-result comparison prompt, confidence threshold → "needs human review", evidence screenshots always attached, results applied only after user review |
| Template formatting drift | Style captured from template cells, golden tests, admin preview before activation |
| Testing against sensitive environments | Allowlist, prod read-only flag, secrets by reference, audit log |
| Android emulator resource heavy / no KVM on server | Separate optional worker host; remote device-farm provider interface |
| LLM cost overruns | Budgets, per-user caps, Haiku for light tasks, caching of story analysis |
| Customer data leakage to LLM | Masking layer, configurable "no real customer data" warning banner on upload |

---

## 16. Delivery Plan (build phases for Claude Code)

Each phase ends with: tests green, `docker compose up` works, a short `docs/progress.md` entry.

**Phase 0 — Scaffold (DoD: `make dev` runs web + api + db + redis + minio; CI lint/test passes)**
Monorepo, Docker Compose, Makefile, env config, FastAPI skeleton with health checks, Next.js skeleton with auth pages, Alembic baseline, pre-commit (ruff, mypy, eslint, prettier), GitHub Actions CI.

**Phase 1 — Auth, RBAC, Admin: types & defaults (DoD: ADM-TT-*, ADM-DC-1..6, ADM-UP-* pass; seed imports 31 defaults from the template)**

**Phase 2 — Document engine (DoD: golden tests 13.4 pass for xlsx and docx using fixture data; template onboarding wizard ADM-TM-* works for the two source templates)**
Build this before AI so the output format is locked early.

**Phase 3 — Projects, suites, generation (DoD: USR-GEN-1..7 pass with FakeLLM; live LLM smoke test passes on the Petty Cash fixture; xlsx download matches template)**
Ingestion, masking, AI client, analysis + generation + post-processing, SSE streaming, grid editor, coverage panel.

**Phase 4 — Suite execution (manual) & reports (DoD: USR-RP-1..4 pass; evidence upload → evidence sheets + hyperlinks; report numbers equal xlsx numbers; bugs & cycles work)**

**Phase 5 — Test Lab: Web (DoD: agent mode + script mode + deterministic defaults run against `infra/demo-target`; results applied to suite; evidence in xlsx)**

**Phase 6 — Test Lab: API (DoD: OpenAPI/Postman/cURL parsing; generated + executed cases against Prism mock; masked logs as evidence images; Postman/pytest export)**

**Phase 7 — Test Lab: Android (DoD: APK upload & analysis; emulator run of a sample APK with evidence; crash detection; provider interface for remote farms)**

**Phase 8 — Hardening (DoD: security checklist Section 12 verified, audit log complete, usage dashboard, retention jobs, performance targets measured, user & admin guide in `docs/`)**

---

## 17. `CLAUDE.md` (place in repo root)

```markdown
# QA Forge — rules for Claude Code
- Source of truth: docs/PRD.md. Build phase by phase (PRD §16). Don't skip DoD.
- Team templates in templates/source/ are READ-ONLY. Always generate outputs by filling
  these templates (openpyxl / docxtpl). Never build xlsx/docx from scratch.
- Keep the template's exact labels and spelling (e.g. "OPERATIONS / SCENERIOS").
- Test case IDs: <Prefix>_<NNN>, continuous across DEFAULT and FUNCTIONAL sections, unique.
- Status enum lives in one place (services/api/app/core/enums.py) — reuse everywhere.
- Every AI call: masking.py first, Pydantic-validated JSON out, prompt files versioned,
  model names from settings only.
- Secrets never reach the LLM or logs; pass secret_ref to runners.
- Every endpoint checks role AND ownership. Add an RBAC test for each new endpoint.
- Write tests with each feature; run `make test` before declaring a task done.
- Record non-obvious decisions in docs/decisions/NNN-title.md.
- Python: ruff + mypy strict on app/. TS: strict mode, no `any` without comment.
```

---

## Appendix A — Pydantic schemas (reference)

```python
class Limit(BaseModel):
    subject: str            # "Cash Centre request amount"
    value: Decimal
    unit: str               # "NGN"
    comparator: Literal["<=", "<", ">=", ">", "=="]
    applies_to: list[str]   # roles/branch types

class AcceptanceCriterion(BaseModel):
    id: str                 # "AC-1"
    text: str
    feature: str

class StoryAnalysis(BaseModel):
    features: list[str]
    actors: list[str]
    acceptance_criteria: list[AcceptanceCriterion]
    business_rules: list[str]
    limits: list[Limit]
    states: list[str]
    approval_chains: list[list[str]]   # [["SSA","FINOPS Officer","FINOPS Verifier"]]
    validations: list[str]
    integrations: list[str]
    out_of_scope: list[str]
    questions: list[str]

class FunctionalCase(BaseModel):
    feature: str
    scenario: str
    steps: list[str] = Field(min_length=1)
    expected_result: str
    priority: Literal["P1","P2","P3","P4"] = "P2"
    techniques: list[Literal["happy_path","boundary_value","equivalence_partition",
        "negative","state_transition","role_based","workflow_routing","validation",
        "search_filter","security","usability","integration"]]
    traces_to: list[str]
    evidence_group: str | None = None
    test_data: dict[str, str] = {}

class ExecutionResult(BaseModel):
    status: Literal["Passed","Failed","Blocked"]
    actual_result: str
    confidence: float = Field(ge=0, le=1)
    notes: str | None = None
```

## Appendix B — XLSX mapping JSON (for the team template)

```json
{
  "main_sheet": "Test Case",
  "header": {
    "project_name": "B1", "user_group_dept": "B2", "solution_provider": "B3",
    "developers": "B4", "test_done_by": "B5", "test_reviewed_by": "B6",
    "start_date": "B7", "end_date": "B8", "test_description": "B9",
    "endpoint_url": "E10"
  },
  "result_analysis": {
    "cases_tested": "E2", "passes": "E3", "failures": "E4", "modification": "E5",
    "not_tested": "E6", "suspended": "E7", "regression": "E8"
  },
  "table": {
    "header_row": 11,
    "columns": { "id": "A", "feature": "B", "scenario": "C", "steps": "D",
                 "expected": "E", "actual": "F", "status": "G", "evidence": "H" },
    "default_banner_text": "DEFAULT SCENARIOS",
    "functional_banner_text": "FUNCTIONAL SCENARIOS",
    "banner_merge": "A:H",
    "first_data_row": 12,
    "merge_feature_column": true,
    "merge_identical_steps": true
  },
  "styles_from": {
    "header_label": "A1", "header_value": "B1", "ra_title": "D1",
    "ra_label": "D2", "ra_value": "E2", "table_header": "A11",
    "banner": "A12", "body": "C13", "id_cell": "A13", "evidence_cell": "H13"
  },
  "font": { "name": "Century Gothic", "size": 9 },
  "date_format": "DD/MM/YYYY",
  "evidence": { "default_sheet": "Default Scenarios", "link_display": "'{sheet}'!A{n}",
                "image_max_width_px": 900 }
}
```

## Appendix C — DOCX token list (tokenised report template)

```
{{ product_name }}
{% for l in pr_links %}{{ l }}{% endfor %}            (hyperlinked, one per line)
{% for v in version_numbers %}{{ v }}{% endfor %}
{{ test_url }}  {{ workitem_url }}  {{ jira_link }}  {{ general_description }}
{{ cert_yes_box }} {{ cert_no_box }}                    (☒ / ☐)
{%tr for f in features %} {{ loop.index }}. | {{ f.name }} | {{ f.description }} |
     {{ f.impl_yes }} Yes {{ f.impl_no }} No | {{ f.func_yes }} Yes {{ f.func_no }} No {%tr endfor %}
{%tr for c in exit_criteria %} {{ loop.index }}. | {{ c }} {%tr endfor %}
{{ ra.test_cycles }} {{ ra.total }} {{ ra.passed }} {{ ra.failed }} {{ ra.unexecuted }}
{{ ra.suspended }} {{ ra.modification }} {{ automation_ratio }}
{{ bugs.raised }} {{ bugs.fixed_retested }} {{ bugs.open }}
{%tr for e in exceptions %} {{ e.id }} | {{ e.status_type }} | {{ e.description }} |
     {{ e.severity }} | {{ e.risk }} {%tr endfor %}          (single N/A row when empty)
{% for p in comments %}{{ p }}{% endfor %}
{%tr for a in approvals %} {{ a.action }} | {{ a.name }} | {{ a.staff_id }} | {{ a.signature }} | {{ a.date }} {%tr endfor %}
{{ classification_label }}                                (footer text box)
```

## Appendix D — Glossary
- **Default scenarios:** reusable non-functional, security and usability cases defined by admin per test-case type.
- **Functional scenarios:** story-specific cases generated by AI from the user story.
- **Evidence group:** the evidence sheet a case's screenshots go to.
- **Test cycle:** one full execution pass of a suite.
- **Agent mode / Script mode:** AI-driven vs recorded-replay execution.
- **CAB:** Change Advisory Board (report certifies readiness for CAB review).
