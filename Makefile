.PHONY: help install install-node build test lint ci ci-native diagram \
	migrate ddl seed seed-sql \
	destroy-data destroy-schema destroy-db destroy destroy-all \
	deploy-destroy destroy-native \
	run-dev setup-native deploy-native deploy-local-native \
	deploy-local deploy-local-logs deploy-local-down deploy-local-clean \
	test-unit test-integration test-e2e test-agent test-hardening test-performance phase7 phase8 \
	ensure-env ensure-venv ensure-node ensure-node-modules

PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
NODE ?= node
NPM ?= npm
COMPOSE := docker compose
IMAGE ?= lms-ai:local
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
SEED ?= 0
DESTROY_YES ?= 0

SQL_DIR := scripts/sql
DESTROY_FLAGS := $(if $(filter 1 true yes,$(DESTROY_YES)),--yes,)

help:
	@echo "LMS-AI build & local deployment"
	@echo ""
	@echo "Development"
	@echo "  make install               Create venv and install Python dev dependencies"
	@echo "  make install-node          Install Node.js deps (diagram tooling, Node 24+)"
	@echo "  make test                  Run all pytest suites"
	@echo "  make test-unit             Unit tests only (no DB)"
	@echo "  make test-integration      Service + DB integration tests"
	@echo "  make test-agent              Phase 8 agent desk tests"
	@echo "  make test-hardening        Phase 7 concurrency + idempotency"
	@echo "  make test-performance      Phase 7 SLO baseline checks"
	@echo "  make phase8                Agent desk tests (G11–G13)"
	@echo "  make diagram               Regenerate docs/diagrams/lms-architecture.tldr"
	@echo "  make lint                  Run ruff and import-linter"
	@echo "  make ci                    Lint + test + Docker build"
	@echo "  make ci-native             Lint + test (no Docker)"
	@echo ""
	@echo "Native (no Docker) — requires local Postgres + DATABASE_URL in .env"
	@echo "  make setup-native          install + migrate (+ SEED=1 for demo data)"
	@echo "  make deploy-native         setup + run API with reload"
	@echo "  make deploy-native SEED=1  deploy + sample data"
	@echo "  make run-dev               Run API only (venv + .env required)"
	@echo "  Staff UI: http://127.0.0.1:8000/staff/  (librarian / changeme)"
	@echo "  make destroy-native        Wipe sample data, schema, and database"
	@echo ""
	@echo "Database & sample data"
	@echo "  make migrate               Alembic upgrade head"
	@echo "  make ddl                   Apply scripts/sql/001_domain_ddl.sql"
	@echo "  make seed                  Migrate + load sample data (Python)"
	@echo "  make seed-sql              Migrate + load sample data (SQL)"
	@echo ""
	@echo "Destroy (teardown)"
	@echo "  make destroy-data          Remove sample seed rows only"
	@echo "  make destroy-schema        Drop all LMS tables"
	@echo "  make destroy-db            Drop + recreate application database"
	@echo "  make destroy               Remove sample data + drop schema"
	@echo "  make destroy-all           data + schema + database"
	@echo "  make destroy-native        Same as destroy-all (no Docker)"
	@echo "  make deploy-destroy        Docker: stop Compose, wipe SQL, remove volumes"
	@echo "                             DESTROY_YES=1 skips confirmation"
	@echo ""
	@echo "Docker"
	@echo "  make build                 Build Docker image ($(IMAGE))"
	@echo "  make deploy-local          Compose: db + api + migrations"
	@echo "  make deploy-local SEED=1   Deploy + load sample data"
	@echo "  make deploy-local-logs     Tail Compose logs"
	@echo "  make deploy-local-down     Stop Compose stack"
	@echo "  make deploy-local-clean    Stop stack and remove volumes"

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -U pip
	$(BIN)/pip install -e ".[dev]"

install-node: ensure-node
	$(NPM) install

build:
	docker build -t $(IMAGE) .

test:
	PYTHONPATH=src $(BIN)/pytest

test-unit:
	PYTHONPATH=src $(BIN)/pytest -m unit

test-integration:
	PYTHONPATH=src $(BIN)/pytest -m integration

test-e2e:
	PYTHONPATH=src $(BIN)/pytest -m e2e

test-agent:
	AGENT_ISSUE_ENABLED=true AGENT_MOCK_LLM=true PYTHONPATH=src $(BIN)/pytest -m agent

test-hardening:
	PYTHONPATH=src $(BIN)/pytest -m hardening

test-performance:
	PYTHONPATH=src $(BIN)/pytest -m performance

phase7: test-hardening test-performance

phase8: test-agent

ensure-node:
	@command -v $(NODE) >/dev/null || { echo "Node.js 24+ required (see .nvmrc)"; exit 1; }
	@$(NODE) -e "const [major]=process.versions.node.split('.').map(Number); if(major<24){console.error('Node.js 24+ required, found '+process.version); process.exit(1)}"

ensure-node-modules: ensure-node
	@test -d node_modules/tldraw || $(NPM) install

diagram: ensure-node-modules
	$(NODE) scripts/generate-architecture-diagram.mjs

lint:
	$(BIN)/ruff check src tests scripts
	PYTHONPATH=src $(BIN)/lint-imports

ci-native: lint test-unit test-integration test-e2e test-agent test-hardening test-performance

ci: ci-native build

migrate: ensure-env ensure-venv
	$(BIN)/python -m alembic upgrade head

ddl: ensure-env ensure-venv
	$(BIN)/python scripts/db_exec.py $(SQL_DIR)/001_domain_ddl.sql

seed: ensure-env ensure-venv migrate
	$(BIN)/python scripts/seed_sample_data.py

seed-sql: ensure-env ensure-venv migrate
	$(BIN)/python scripts/db_exec.py $(SQL_DIR)/002_sample_data.sql

destroy-data: ensure-env ensure-venv
	@chmod +x scripts/destroy.sh scripts/seed.sh scripts/deploy-native.sh 2>/dev/null || true
	./scripts/destroy.sh --data $(DESTROY_FLAGS)

destroy-schema: ensure-env ensure-venv
	@chmod +x scripts/destroy.sh scripts/seed.sh scripts/deploy-native.sh 2>/dev/null || true
	./scripts/destroy.sh --schema $(DESTROY_FLAGS)

destroy-db: ensure-env ensure-venv
	@chmod +x scripts/destroy.sh scripts/seed.sh scripts/deploy-native.sh 2>/dev/null || true
	./scripts/destroy.sh --db $(DESTROY_FLAGS)

destroy: ensure-env ensure-venv
	@chmod +x scripts/destroy.sh scripts/seed.sh scripts/deploy-native.sh 2>/dev/null || true
	./scripts/destroy.sh --data --schema $(DESTROY_FLAGS)

destroy-all destroy-native: ensure-env ensure-venv
	@chmod +x scripts/destroy.sh scripts/seed.sh scripts/deploy-native.sh 2>/dev/null || true
	./scripts/destroy.sh --all $(DESTROY_FLAGS)

deploy-destroy:
	@chmod +x scripts/destroy.sh scripts/deploy-local.sh scripts/deploy-native.sh scripts/seed.sh 2>/dev/null || true
	./scripts/destroy.sh --deploy $(DESTROY_FLAGS)

setup-native: ensure-env ensure-venv migrate
	@if [ "$(SEED)" = "1" ]; then $(MAKE) seed; fi
	@echo "Native setup complete. Run: make run-dev  or  make deploy-native"

run-dev: ensure-env ensure-venv
	$(BIN)/uvicorn lms.main:app --reload --app-dir src --host $(API_HOST) --port $(API_PORT)

deploy-native deploy-local-native:
	@chmod +x scripts/deploy-native.sh 2>/dev/null || true
	SEED=$(SEED) API_HOST=$(API_HOST) API_PORT=$(API_PORT) ./scripts/deploy-native.sh

ensure-env:
	test -f .env || cp .env.example .env

ensure-venv:
	@if ! test -x $(BIN)/python; then \
		$(MAKE) install; \
	elif ! test -f $(VENV)/pyvenv.cfg || ! grep -qF "$(abspath $(VENV))" $(VENV)/pyvenv.cfg; then \
		echo "Recreating virtualenv (stale paths after project move)..."; \
		rm -rf $(VENV); \
		$(MAKE) install; \
	elif ! $(BIN)/python -m alembic --version >/dev/null 2>&1; then \
		echo "Repairing virtualenv (reinstalling console scripts)..."; \
		$(BIN)/python -m pip install -U pip; \
		$(BIN)/python -m pip install -e ".[dev]"; \
	fi

deploy-local:
	@chmod +x scripts/deploy-local.sh scripts/destroy.sh 2>/dev/null || true
	test -f .env || cp .env.example .env
	SEED=$(SEED) ./scripts/deploy-local.sh

deploy-local-logs:
	$(COMPOSE) logs -f api db

deploy-local-down:
	$(COMPOSE) down

deploy-local-clean:
	$(COMPOSE) down -v
