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

**Not yet verified** (the first machine blocked process launches)
- Web: `npm run lint`, `typecheck`, `test`, `build`.
- `make dev`, `docker compose up`, CI run on GitHub.

**Next**
1. On an unrestricted machine: `make install && make lint && make test && make dev`.
2. Fix anything red, then close Phase 0 and start Phase 1 (auth, RBAC, types & defaults).
