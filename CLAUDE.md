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
