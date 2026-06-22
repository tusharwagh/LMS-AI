# LMS-AI — K-12 Library Management (MVP)

Python **modular monolith** for K-12 school library circulation: reference data, catalog, loans, staff workflows, a React staff desk, and an optional **AI-assisted circulation agent** (Phase 8).

**Status:** Phases **0–8 code-complete** — deterministic desk workflows (WF-01/WF-02), JWT auth, hardening tests, and conversational agent desk behind `AGENT_ISSUE_ENABLED`. Go-live sign-off (G1–G13) is tracked in [go-live-checklist.md](docs/go-live-checklist.md).

| Doc | Purpose |
|-----|---------|
| [MVP.md](docs/MVP.md) | Requirements, architecture, agent spec (§2.2), traceability |
| [plan-mvp.md](docs/plan-mvp.md) | Phased implementation plan (§0 status) |
| [runbook.md](docs/runbook.md) | Deploy, backup, agent/LLM env (§10), incidents |
| [go-live-checklist.md](docs/go-live-checklist.md) | Pre-production verification (G1–G13) |
| [research.md](docs/research.md) | Design history; agent governance (§15) |

**Agent governance:** IMDA MGF v1.5 + Twelve-Factor deployment — [`.cursor/skills/imda-agentic-ai-governance/SKILL.md`](.cursor/skills/imda-agentic-ai-governance/SKILL.md)

---

## What ships

| Capability | Notes |
|------------|-------|
| **Reference / Catalog / Loan** | DDD bounded contexts; REST under `/api/v1/*` |
| **Desk workflows** | Search & issue, return, delivery / pick-up fulfillment |
| **Staff UI** | React CRM at `/staff/` — wizards, **AI assist**, **Dashboard** + **LLM costs** (Administration) |
| **Reporting** | Dashboard + custom reports (JSON/CSV); `GET /api/v1/reporting/*`; holdings include **DAMAGED** / **LOST** |
| **Agent desk** | Natural-language issue, return, catalog browse, patron lookup, issued-books inquiry |
| **HITL** | Librarian approves all writes via approval cards + `/resume` |
| **LLM routing** | LiteLLM **Router** (`src/lms/shared/llm/`) — cache, RPM, fallbacks; rule-based parser in CI |
| **LLM spend** | Postgres `llm_spend_logs`; staff API + UI; Langfuse traces when configured |
| **Observability** | structlog → stdout; optional Langfuse traces (`make validate-langfuse`) |

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| **Python** | 3.12+ | Required for native dev and tests |
| **Node.js** | 24+ | `make staff-ui-build`, `make diagram` (see `.nvmrc`) |
| **PostgreSQL** | 16 | Required for native deploy; bundled in Docker path |
| **Docker + Compose** | recent | Optional; easiest path for a fresh machine |
| **Make** | any | All build/deploy targets |
| **Git** | any | Clone and CI |

---

## Rebuild from scratch (new environment)

### 1. Clone and configure

```bash
git clone https://github.com/tusharwagh/LMS-AI.git
cd LMS-AI

cp .env.example .env
# Edit .env for production: APP_SECRET_KEY, DATABASE_URL (native), CORS_ORIGINS
```

### 2. Choose a deploy path

**Docker (recommended on a clean machine)** — Postgres and API start together; no local DB install needed.

```bash
make deploy-local              # build image, start db + api, run migrations
make deploy-local SEED=1       # + demo patrons, holdings, rule sets
```

**Native (no Docker)** — use when PostgreSQL is already installed locally.

```bash
# Create database and user matching .env.example, e.g.:
#   createdb lms
#   createuser -P lms   # password: lms

make deploy-native              # venv, migrate, run API with reload
make deploy-native SEED=1       # + sample data
```

Step-by-step native alternative:

```bash
make install
make staff-ui-build             # React staff desk → src/lms/staff/static/
make setup-native SEED=1        # migrate + optional seed only
make run-dev                    # API only (Uvicorn with reload)
```

### 3. Verify the stack

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok"}

# JWT login (demo password below)
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token \
  -d "username=librarian&password=changeme"
```

| URL | Purpose |
|-----|---------|
| `http://127.0.0.1:8000/health` | Liveness |
| `http://127.0.0.1:8000/docs` | OpenAPI / Swagger (Authorize with JWT) |
| `http://127.0.0.1:8000/staff/` | Staff desk UI (wizards + AI assist) |

Staff UI login: **`librarian`** / **`changeme`** (dev only).

### 4. Run tests (after deploy path has applied migrations)

```bash
make ci-native                # lint + full pytest (recommended pre-PR gate)
make test-unit                # no database
make test-integration         # services + orchestrator + DB
make test-e2e                 # HTTP journeys + staff UI smoke (excludes Playwright)
make test-e2e-playwright      # browser E2E (login, wizards, agent HITL)
make test-agent               # Phase 8 agent desk (mock LLM)
make phase7                   # concurrency, idempotency, SLO baselines
make phase8                   # alias for test-agent
```

For native tests, Postgres must be running and `DATABASE_URL` in `.env` must match the test database.

### Debug in Cursor (breakpoints)

1. `make install` and ensure Postgres is up (`make migrate` or `make setup-native`).
2. Open **Run and Debug** (sidebar) or press **F5**.
3. Choose **LMS API (breakpoints)** — reliable breakpoints (no hot reload).
   - Use **LMS API (reload + breakpoints)** if you need `--reload` (may need `subProcess` attach on reload).
4. Set breakpoints in `src/lms/` (e.g. `agent/coordinator.py`), then hit the API or staff UI.

Other launch configs: **Pytest: current file**, **Pytest: agent tests** (sets `AGENT_ISSUE_ENABLED`).

| Mode | Use when |
|------|----------|
| Cursor **LMS API (breakpoints)** | Step through request handlers with F5/F10 |
| `make run-dev-debug` | Verbose uvicorn logs only (no debugger attach) |
| `DEBUG=1 make run-dev` | Same as run-dev-debug from terminal |

Shared config lives in [`.vscode/launch.json`](.vscode/launch.json). Install the recommended **Python** extension if prompted.

### 5. Tear down (dev only)

```bash
make deploy-destroy DESTROY_YES=1    # Docker: stop stack, wipe SQL, remove volumes
make destroy-native DESTROY_YES=1    # Native: wipe data, schema, and database
```

---

## Environment variables

Copy [`.env.example`](.env.example) to `.env`. All config follows **Twelve-Factor** discipline — secrets and toggles in env, not in code or prompts.

### Core

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_ENV` | `development` | Runtime environment |
| `APP_DEBUG` | `true` | Debug mode (`false` in production) |
| `APP_SECRET_KEY` | `change-me-in-production` | JWT signing — **change in production** |
| `DATABASE_URL` | `postgresql+psycopg://lms:lms@localhost:5432/lms` | SQLAlchemy URL (native) |
| `JWT_ALGORITHM` | `HS256` | Token algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Token lifetime |
| `LIBRARY_TIMEZONE` | `Asia/Kolkata` | Library-local dates |
| `CORS_ORIGINS` | `*` | Comma-separated origins (explicit list in production) |

Docker Compose overrides `DATABASE_URL` to point at the `db` service. Optional ports: `LMS_DB_PORT`, `LMS_API_PORT`.

### Agent desk (Phase 8)

Disabled by default. See [runbook.md §10](docs/runbook.md) for production guidance.

| Variable | Default | Purpose |
|----------|---------|---------|
| `AGENT_ISSUE_ENABLED` | `false` | Enable conversational agent API + AI assist |
| `AGENT_MOCK_LLM` | `true` | `true` = rule-based intent parser (CI/dev); `false` = live LLM |
| `LLM_PROVIDER` | `groq` | Primary: `groq`, `openai`, `anthropic`, `together`, `huggingface` |
| `LLM_PROVIDERS` | *(empty)* | Optional chain, e.g. `groq,openai` |
| `GROQ_API_KEY`, `OPENAI_API_KEY`, … | — | Provider keys (set only what you use) |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Default model for primary provider |
| `AGENT_MAX_TOOL_CALLS_PER_TURN` | `5` | Bounded tool loop per message |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` | — | Agent audit traces (required in production when agent enabled) |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Langfuse project host |

**Dev example (agent on, mock LLM — no API keys):**

```env
AGENT_ISSUE_ENABLED=true
AGENT_MOCK_LLM=true
```

**Staging example (live intent parsing):**

```env
AGENT_ISSUE_ENABLED=true
AGENT_MOCK_LLM=false
LLM_PROVIDER=groq
GROQ_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
```

Validate Langfuse connectivity: `make validate-langfuse`

---

## Authentication (JWT)

All `/api/v1/*` endpoints require a **Bearer JWT** except `GET /health` and `POST /api/v1/auth/token`.

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token \
  -d "username=librarian&password=changeme"

curl -H "Authorization: Bearer <access_token>" \
  http://127.0.0.1:8000/api/v1/reference/patron-types
```

Default users (created by `make seed` / `SEED=1`). Python seed loads **~1,614** library rows (demo + bulk K-12 data); see [runbook.md §5](docs/runbook.md).

| Username | Role | Password (dev) |
|----------|------|----------------|
| `admin` | ADMIN | `changeme` |
| `librarian` | LIBRARIAN | `changeme` |
| `patron` | PATRON | `changeme` |

In Swagger (`/docs`), use **Authorize** with the raw `access_token` (no `Bearer ` prefix).

---

## Agent desk (Phase 8)

Conversational circulation for librarians — governed per [research.md §15](docs/research.md) (IMDA MGF + Twelve-Factor).

| Flow | Example staff message |
|------|------------------------|
| Guided issue | “I want to issue a book” → patron → criteria → search → HITL commit |
| One-shot issue | “Issue Harry Potter to Riya, desk pickup” |
| Issued books | “What books are issued to Riya?” |
| Return | “Return barcode ABC-123” / guided return |
| Catalog browse | “Browse catalog” / “mystery novels” |
| Patron lookup | “Lookup patron Riya Sharma” |

**API** (requires `AGENT_ISSUE_ENABLED=true` and librarian JWT):

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/api/v1/agent/issue/sessions` | Start session |
| `POST` | `/api/v1/agent/issue/sessions/{id}/message` | Send NL message |
| `POST` | `/api/v1/agent/issue/sessions/{id}/resume` | Approve / deny pending action |
| `GET` | `/api/v1/agent/issue/sessions/{id}` | Session summary |

All **writes** (issue, return, cancel, fulfillment transition) require explicit librarian approval — deny-by-default. Staff-facing copy is built in `src/lms/agent/messages.py`; the UI renders API text verbatim.

**Key modules:** `coordinator.py`, `tools.py`, `intent_parser.py`, `llm_intent_prompt.py`, `shared/llm/` (Router gateway + spend logger), `tracing.py`

**LLM cost reporting** (librarian/admin JWT or staff UI **Administration → LLM costs**):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/llm-spend/logs` | Paginated spend log (filters: date, purpose, session, operator) |
| `GET` | `/api/v1/llm-spend/summary` | Aggregates by purpose / model / provider |

Apply migration `005_llm_spend_logs` (`make migrate`) before spend logging in dev/prod.

**Circulation reporting** (librarian/admin JWT or staff UI **Administration → Dashboard**):

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/api/v1/reporting/dashboard` | Holdings by status, active/overdue loans, today’s activity, daily series |
| `POST` | `/api/v1/reporting/reports/generate` | Custom metrics report (JSON or CSV download) |
| `GET` | `/api/v1/reporting/reports/presets` | Named preset definitions for report builder |

Metrics: `daily_issues`, `daily_returns`, `holdings_by_status`, `total_active_loans`, `overdue_loans`. Presets include `daily_circulation`, `holdings_snapshot`, `loan_health`, `full_dashboard`.

```bash
# Dashboard (query param days=7..90, or from_date + to_date together)
curl -H "Authorization: Bearer $TOKEN" \
  "http://127.0.0.1:8000/api/v1/reporting/dashboard?days=30"

# Custom JSON report
curl -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"metrics":["daily_issues","daily_returns"],"from_date":"2026-06-01","to_date":"2026-06-13"}' \
  "http://127.0.0.1:8000/api/v1/reporting/reports/generate"
```

---

## Build & deploy reference

| Target | Command | Purpose |
|--------|---------|---------|
| Install (native dev) | `make install` | venv + editable install with dev tools |
| Staff UI build | `make staff-ui-build` | React → `src/lms/staff/static/` |
| Node deps (diagram) | `make install-node` | `npm install` for tldraw diagram script |
| Regenerate diagram | `make diagram` | Requires Node.js 24+ |
| CI (no Docker) | `make ci-native` | ruff + import-linter + mypy + full pytest (**211** tests) |
| CI parity | `make ci` | lint + test + Docker build |
| **CI ship** | `make ci-ship` | `ci-native`, then interactive commit + push (`scripts/ci_commit_push.sh`) |
| Langfuse check | `make validate-langfuse` | Auth + test span (skips if keys unset) |
| **Native deploy** | `make deploy-native` | No Docker — venv + migrate + API |
| Native deploy + seed | `make deploy-native SEED=1` | Deploy + demo data |
| Native teardown | `make destroy-native` | Wipe data, schema, database |
| Native setup only | `make setup-native` | install + migrate (no server) |
| Native dev server | `make run-dev` | Uvicorn with reload only |
| Docker deploy | `make deploy-local` | Compose: Postgres + migrate + API |
| Docker teardown | `make deploy-destroy` | Stop stack, wipe SQL, remove volumes |

Run `make help` for the full target list.

---

## Tests

| Layer | Path | Marker / command |
|-------|------|------------------|
| Unit | `tests/unit/` | `@pytest.mark.unit` — includes reporting RBAC/schemas |
| Integration | `tests/integration/` | `@pytest.mark.integration` — includes reporting dashboard/generate |
| E2E | `tests/e2e/` | `@pytest.mark.e2e` |
| Agent | `tests/agent/` | `@pytest.mark.agent` — `make test-agent` |
| Hardening | `tests/hardening/` | `@pytest.mark.hardening` — `make test-hardening` |
| Performance | `tests/performance/` | `@pytest.mark.performance` — `make test-performance` |

Recommended before merge: `make lint && make ci-native` (211 tests)

---

## Schema & sample data

- **Migrations (authoritative):** `alembic/versions/` — applied via `make migrate`
- **DDL reference:** [scripts/sql/001_domain_ddl.sql](scripts/sql/001_domain_ddl.sql)
- **Seed SQL:** [scripts/sql/002_sample_data.sql](scripts/sql/002_sample_data.sql)
- **Destroy:** [scripts/sql/003_destroy_sample_data.sql](scripts/sql/003_destroy_sample_data.sql), [scripts/sql/004_destroy_schema.sql](scripts/sql/004_destroy_schema.sql)

Or use `make seed` / `make destroy-native`.

---

## Project layout

```
src/lms/
  api/           # FastAPI app, auth, workflow coordinators, agent router
  agent/         # Desk agent: coordinator, tools, intent, LLM, tracing
  reference/     # Patrons, types, class sections
  catalog/       # Bibliographic records, holdings
  loan/          # Circulation, orchestrator, fulfillment
  reporting/     # Dashboard + custom reports (read-only bounded context)
  staff/ui/      # React + Vite source (CRM + AI assist + Dashboard)
  staff/static/  # Built staff desk (not committed — make staff-ui-build)
  config.py      # pydantic-settings (Twelve-Factor config)
alembic/         # Database migrations
scripts/         # Deploy, seed, SQL helpers
tests/           # unit, integration, e2e, agent, hardening, performance
docs/            # MVP spec, domain models, runbook, governance notes
.cursor/skills/  # Agent governance (IMDA + Twelve-Factor), DDD, code analysis
```

**CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on push/PR to `main` (`make ci-native`; `setup-python@v6`). Local ship gate: `make ci-ship`.

**Architecture boundaries:** enforced by `import-linter` — agent module must not import domain `infrastructure` directly.

---

## API surface (MVP)

| Prefix | Domain |
|--------|--------|
| `/api/v1/auth` | JWT token and current user |
| `/api/v1/reference` | Patron types, class sections, patrons |
| `/api/v1/catalog` | Records, holdings, search |
| `/api/v1/loan` | Checkouts, returns, overdue, rules |
| `/api/v1/workflows` | WF-01 issue, WF-02 return (desk + delivery/pick-up) |
| `/api/v1/llm-spend` | LLM cost logs and summary (staff/admin) |
| `/api/v1/reporting` | Dashboard and customizable circulation reports (staff/admin) |
| `/api/v1/agent/issue` | Conversational agent desk (Phase 8; feature-flagged) |
| `/staff/` | Staff browser UI |

---

## Production notes

- Set a strong `APP_SECRET_KEY`, explicit `CORS_ORIGINS`, and `APP_DEBUG=false` — startup rejects insecure defaults when `APP_ENV=production`.
- Change all default passwords; rotate secrets before go-live.
- Follow [go-live-checklist.md](docs/go-live-checklist.md) (G1–G13) and [runbook.md](docs/runbook.md).
- Run `make phase7` as the hardening gate; `make ci-native` before every release.
- **Agent pilot:** enable only after G11–G13 sign-off; set provider keys + Langfuse; never commit `.env`.
- **Twelve-Factor:** build/test in CI → deploy immutable artifact → run processes separately; admin via `make migrate` / `make seed`, not agent tools.
- **Session store (MVP):** agent sessions are in-process RAM — run a single API worker per desk deployment until a durable store is added (see [research.md §15.9](docs/research.md)).
