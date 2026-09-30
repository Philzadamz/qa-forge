# 001 — Local development without Docker

**Status:** accepted (temporary) · **Date:** 2026-09-30

## Context
The PRD (§4.1) mandates PostgreSQL, Redis and MinIO via Docker Compose. The first
development machine (managed corporate Windows laptop) has no Docker, and Docker Desktop
needs admin rights and a paid licence at Sterling's size.

## Decision
Support two run modes from the same code:

| Concern | Local mode (default) | Docker mode |
|---|---|---|
| Database | SQLite file in `var/` | PostgreSQL 16 |
| Object storage | `LocalStorage` under `var/storage` | S3/MinIO (backend added later) |
| Queue | In-process jobs (`REDIS_URL` empty) | Redis + arq |

To keep both working:
- ORM columns use portable types: `Uuid`, `JSON` with a JSONB variant on Postgres, and
  array-like fields (e.g. `developers TEXT[]`) stored as JSON lists.
- Alembic runs with `render_as_batch=True` so ALTER TABLE works on SQLite.
- Storage and queue sit behind interfaces chosen by settings.

## Consequences
- `docker-compose.yml` is authored but unverified until run on a machine with Docker.
- Postgres-only features (GIN indexes on JSONB, array operators) are off-limits unless
  guarded by dialect.
- CI (ubuntu) should add a Postgres service job before Phase 3 so both dialects are tested.
