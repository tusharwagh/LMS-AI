.PHONY: help install install-node build test lint ci ci-native ci-ship check-traceability \
	check-standards standards-materialize standards-upgrade standards-contribute verify-phase3 verify-phase4 verify-phase5 \
	diagram \
	migrate ddl seed seed-sql \
	destroy-data destroy-schema destroy-db destroy destroy-all \
	deploy-destroy destroy-native \
	run-dev run-dev-debug setup-native deploy-native deploy-local-native \
	deploy-local deploy-local-logs deploy-local-down deploy-local-clean \
	test-unit test-integration test-e2e test-e2e-playwright test-agent test-hardening test-performance phase7 phase8 \
	staff-ui-install staff-ui-build staff-ui-typecheck staff-ui-dev validate-langfuse \
	ensure-env ensure-venv ensure-node ensure-node-modules ensure-staff-ui

PYTHON ?= python3
VENV ?= .venv
BIN := $(VENV)/bin
NODE ?= node
NPM ?= npm
PLAYWRIGHT_BROWSERS_PATH ?= $(CURDIR)/.playwright-browsers
# Outside OneDrive — avoids corrupted SQLite shards and sync stalls during mypy.
MYPY_CACHE_DIR ?= /tmp/lms-ai-mypy-cache
export MYPY_CACHE_DIR
STANDARDS_CI_POLICY := $(shell tr -d '[:space:]' < .standards-ci-policy 2>/dev/null || echo fail)
STANDARDS_ENV = STANDARDS_ROOT=$(CURDIR) STANDARDS_REFERENCE=standards \
	STANDARDS_MANIFEST=standards/manifest.json \
	STANDARDS_VERSION_FILE=.standards-version \
	STANDARDS_LATEST_FILE=.standards-latest \
	STANDARDS_PROFILES_FILE=.standards-profiles \
	CI_POLICY=$(STANDARDS_CI_POLICY)

IMAGE ?= lms-ai:local
API_HOST ?= 127.0.0.1
API_PORT ?= 8000
SEED ?= 0
DESTROY_YES ?= 0
DEBUG ?= 0

# DEBUG=1 → APP_DEBUG=true + uvicorn --log-level debug (overrides .env for this process)
ifeq ($(filter 1 true yes,$(DEBUG)),)
UVICORN := $(BIN)/uvicorn lms.main:app --reload --app-dir src --host $(API_HOST) --port $(API_PORT) --log-level info
else
UVICORN := APP_DEBUG=true $(BIN)/uvicorn lms.main:app --reload --app-dir src --host $(API_HOST) --port $(API_PORT) --log-level debug
endif

SQL_DIR := scripts/sql
DESTROY_FLAGS := $(if $(filter 1 true yes,$(DESTROY_YES)),--yes,)

help:
	@echo "LMS-AI build & local deployment"
	@echo ""
	@echo "Development"
	@echo "  make install               Create venv and install Python dev dependencies"
	@echo "  make install-node          Install Node.js deps (diagram tooling, Node 24+)"
	@echo "  make staff-ui-build        Build React staff desk to src/lms/staff/static/ (not committed)"
	@echo "  make staff-ui-typecheck    Typecheck staff desk UI"
	@echo "  make test                  Run all pytest suites"
	@echo "  make test-unit             Unit tests only (no DB)"
	@echo "  make test-integration      Service + DB integration tests"
	@echo "  make test-e2e              HTTP journeys + staff UI smoke tests"
	@echo "  make test-e2e-playwright   Browser E2E (login, issue/return wizards, agent HITL)"
	@echo "  make test-agent              Phase 8 agent desk tests"
	@echo "  make validate-langfuse       Check Langfuse keys + emit test span"
	@echo "  make test-hardening        Phase 7 concurrency + idempotency"
	@echo "  make test-performance      Phase 7 SLO baseline checks"
	@echo "  make phase8                Agent desk tests (G11–G13)"
	@echo "  make diagram               Regenerate docs/diagrams/lms-architecture.tldr"
	@echo "  make lint                  Run ruff, import-linter, and mypy"
	@echo "  make clean-mypy-cache      Remove mypy cache (fix INTERNAL ERROR / timeouts)"
	@echo "  make ci                    Lint + test + Docker build"
	@echo "  make ci-native             Lint + test (no Docker)"
	@echo "  make ci-ship               ci-native, then prompt commit message and push"
	@echo "  make check-traceability    Verify PR body has issue + REQ (PR_BODY_FILE=...)"
	@echo "  make check-standards       Template drift check (warn-only; Phase 3 pilot)"
	@echo "  make standards-materialize Copy standards/ → .cursor/ managed paths"
	@echo "  make standards-upgrade     Bump submodule pin + re-materialize (VERSION=1.0.1)"
	@echo ""
	@echo "Native (no Docker) — requires local Postgres + DATABASE_URL in .env"
	@echo "  make setup-native          install + migrate (+ SEED=1 for demo data)"
	@echo "  make deploy-native         setup + run API with reload"
	@echo "  make deploy-native SEED=1  deploy + sample data"
	@echo "  make deploy-native DEBUG=1 deploy + debug mode"
	@echo "  make run-dev               Run API only (venv + .env required)"
	@echo "  make run-dev-debug         Verbose logs (APP_DEBUG=true); not for IDE breakpoints"
	@echo "  Cursor: Run and Debug (F5) → LMS API (breakpoints) — see README"
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
	@echo "  make build                 Validate Langfuse (if configured) + Docker image ($(IMAGE))"
	@echo "  make deploy-local          Compose: db + api + migrations"
	@echo "  make deploy-local SEED=1   Deploy + load sample data"
	@echo "  make deploy-local-logs     Tail Compose logs"
	@echo "  make deploy-local-down     Stop Compose stack"
	@echo "  make deploy-local-clean    Stop stack and remove volumes"

install:
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install -U pip
	$(BIN)/pip install -e ".[dev]"

STAFF_UI_DIR := src/lms/staff/ui

install-node: ensure-node
	$(NPM) install

staff-ui-install: ensure-node
	cd $(STAFF_UI_DIR) && $(NPM) install

staff-ui-build: staff-ui-install
	cd $(STAFF_UI_DIR) && $(NPM) run build

staff-ui-typecheck: staff-ui-install
	cd $(STAFF_UI_DIR) && $(NPM) run typecheck

staff-ui-dev: staff-ui-install
	cd $(STAFF_UI_DIR) && $(NPM) run dev

ensure-staff-ui:
	@test -f src/lms/staff/static/index.html || $(MAKE) staff-ui-build

build: validate-langfuse
	docker build -t $(IMAGE) .

test:
	PYTHONPATH=src $(BIN)/pytest

test-unit:
	PYTHONPATH=src $(BIN)/pytest -m unit

test-integration:
	PYTHONPATH=src $(BIN)/pytest -m integration

test-e2e: ensure-staff-ui
	PYTHONPATH=src $(BIN)/pytest -m "e2e and not playwright"

test-e2e-playwright: ensure-staff-ui ensure-playwright
	PLAYWRIGHT_BROWSERS_PATH=$(PLAYWRIGHT_BROWSERS_PATH) PYTHONPATH=src $(BIN)/pytest -m playwright

ensure-playwright:
	PLAYWRIGHT_BROWSERS_PATH=$(PLAYWRIGHT_BROWSERS_PATH) $(BIN)/playwright install chromium

test-agent:
	AGENT_ISSUE_ENABLED=true AGENT_MOCK_LLM=true PYTHONPATH=src $(BIN)/pytest -m agent

validate-langfuse: ensure-venv
	@PYTHONPATH=src $(BIN)/python scripts/validate_langfuse.py

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

clean-mypy-cache:
	rm -rf .mypy_cache "$(MYPY_CACHE_DIR)"

lint:
	$(BIN)/ruff check src tests scripts
	PYTHONPATH=src $(BIN)/lint-imports
	$(BIN)/mypy

check-traceability:
	@chmod +x scripts/check_pr_traceability.sh
	@./scripts/check_pr_traceability.sh

check-standards:
	@test -d standards/scripts || (echo "standards/ submodule missing — run: git submodule update --init standards" && exit 1)
	@chmod +x standards/scripts/check-standards.sh
	@$(STANDARDS_ENV) ./standards/scripts/check-standards.sh; rc=$$?; \
	 if [ $$rc -eq 2 ]; then echo "check-standards: warn (non-blocking)"; exit 0; fi; \
	 exit $$rc

standards-materialize:
	@test -d standards/bootstrap || (echo "standards/ submodule missing" && exit 1)
	@chmod +x standards/bootstrap/standards-materialize.sh
	@$(STANDARDS_ENV) ./standards/bootstrap/standards-materialize.sh

standards-upgrade:
	@chmod +x scripts/standards-upgrade.sh
	@./scripts/standards-upgrade.sh $(VERSION)

standards-contribute:
	@test -x standards/scripts/standards-contribute.sh || (echo "standards-contribute missing — upgrade standards/ submodule to v1.0.2+" && exit 1)
	@chmod +x standards/scripts/standards-contribute.sh
	@$(STANDARDS_ENV) OPEN=$(OPEN) ./standards/scripts/standards-contribute.sh

verify-phase3:
	@chmod +x scripts/verify-phase3.sh
	@./scripts/verify-phase3.sh

verify-phase4:
	@chmod +x scripts/verify-phase4.sh
	@./scripts/verify-phase4.sh

verify-phase5:
	@chmod +x scripts/verify-phase5.sh
	@./scripts/verify-phase5.sh

ci-native: install lint staff-ui-build staff-ui-typecheck test-unit test-integration test-e2e test-e2e-playwright test-agent test-hardening test-performance check-standards

ci-ship:
	@chmod +x scripts/ci_commit_push.sh
	PLAYWRIGHT_BROWSERS_PATH=$(PLAYWRIGHT_BROWSERS_PATH) ./scripts/ci_commit_push.sh

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

setup-native: ensure-env ensure-venv migrate staff-ui-build
	@if [ "$(SEED)" = "1" ]; then $(MAKE) seed; fi
	@echo "Native setup complete. Run: make run-dev  or  make deploy-native"

run-dev: ensure-env ensure-venv
	$(UVICORN)

run-dev-debug:
	$(MAKE) run-dev DEBUG=1

deploy-native deploy-local-native:
	@chmod +x scripts/deploy-native.sh 2>/dev/null || true
	DEBUG=$(DEBUG) SEED=$(SEED) API_HOST=$(API_HOST) API_PORT=$(API_PORT) ./scripts/deploy-native.sh

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
