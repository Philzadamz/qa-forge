# QA Forge — developer commands. Requires: uv, Node 20+, npm, make.
# Local mode (no Docker) uses SQLite + local storage; see docs/decisions/001.

API_DIR := services/api
WEB_DIR := apps/web
UV := uv --directory $(API_DIR)

.PHONY: help install dev dev-api dev-web migrate test test-api test-web lint lint-api lint-web \
        format typecheck up down seed-admin

help:
	@echo "install     Install API (uv) and web (npm) dependencies"
	@echo "dev         Run API (:8000) and web (:3000) together, local mode"
	@echo "migrate     Apply database migrations"
	@echo "test        Run all tests"
	@echo "lint        Run ruff, mypy, eslint, prettier, tsc"
	@echo "up / down   Start / stop the full Docker Compose stack"

install:
	$(UV) sync
	cd $(WEB_DIR) && npm ci

migrate:
	$(UV) run alembic upgrade head

dev-api: migrate
	$(UV) run uvicorn app.main:app --reload --port 8000

dev-web:
	cd $(WEB_DIR) && npm run dev

dev:
	$(MAKE) -j2 dev-api dev-web

test: test-api test-web

test-api:
	$(UV) run pytest

test-web:
	cd $(WEB_DIR) && npm test

lint: lint-api lint-web

lint-api:
	$(UV) run ruff check .
	$(UV) run ruff format --check .
	$(UV) run mypy

lint-web:
	cd $(WEB_DIR) && npm run lint && npm run format:check && npm run typecheck

format:
	$(UV) run ruff check --fix .
	$(UV) run ruff format .
	cd $(WEB_DIR) && npm run format

up:
	docker compose up -d --build

down:
	docker compose down

# Implemented in Phase 1.
seed-admin:
	$(UV) run python -m app.cli seed-admin --email "$(EMAIL)" --password "$(PASSWORD)"
