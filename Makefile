.PHONY: help install build test lint ci ci-native diagram \
	migrate ddl seed seed-sql \
	destroy-data destroy-schema destroy-db destroy destroy-all \
	deploy-destroy destroy-native \
	run-dev setup-native deploy-native deploy-local-native \
	deploy-local deploy-local-logs deploy-local-down deploy-local-clean \
	test-unit test-integration test-e2e test-hardening test-performance phase7 \
	ensure-env ensure-venv

PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
COMPOSE := docker compose
IMAGE ?= lms:local
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
SEED ?= 0
DESTROY_YES ?= 0

SQL_DIR := scripts/sql
DESTROY_FLAGS := $(if $(filter 1 true yes,$(DESTROY_YES)),--yes,)

help:
	@echo "LMS build & local deployment"
	@echo ""
	@echo "Development"
	@echo "  make install               Create venv and install dev dependencies"
	@echo "  make test                  Run all pytest suites"
	@echo "  make test-unit             Unit tests only (no DB)"
	@echo "  make test-integration      Service + DB integration tests"
	@echo "  make test-e2e              Full HTTP journey tests"
	@echo "  make test-hardening        Phase 7 concurrency + idempotency"
	@echo "  make test-performance      Phase 7 SLO baseline checks"
	@echo "  make phase7                Hardening + performance (go-live gate)"
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

test-hardening:
	PYTHONPATH=src $(BIN)/pytest -m hardening

test-performance:
	PYTHONPATH=src $(BIN)/pytest -m performance

phase7: test-hardening test-performance

diagram:
	node scripts/generate-architecture-diagram.mjs

lint:
	$(BIN)/ruff check src tests scripts
	PYTHONPATH=src $(BIN)/lint-imports lint

ci-native: lint test-unit test-integration test-e2e test-hardening test-performance

ci: ci-native build

migrate: ensure-env ensure-venv
	$(BIN)/alembic upgrade head

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
	test -x $(BIN)/python || $(MAKE) install

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
