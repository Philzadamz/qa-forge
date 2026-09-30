# QA Forge

AI-assisted test case generation, QA reporting and test execution. Spec: [docs/PRD.md](docs/PRD.md).
Build status: [docs/progress.md](docs/progress.md).

## Quick start (local mode — no Docker)

Requires [uv](https://docs.astral.sh/uv/), Node 20.19+ (22 LTS recommended), npm and make.

```sh
cp .env.example .env
# Copy the two team templates into templates/source/ (see templates/source/README.md)
make install
make dev          # API on :8000, web on :3000
make test
```

## With Docker

```sh
make up           # postgres, redis, minio, api, web
```
