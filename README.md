# LMS-AI — K-12 Library Management (MVP)

Python **modular monolith** for K-12 school library circulation: reference data, catalog, loans, staff workflows, and a desk UI.

| Doc | Purpose |
|-----|---------|
| [MVP.md](docs/MVP.md) | Requirements, architecture, traceability |
| [plan-mvp.md](docs/plan-mvp.md) | Phased implementation plan |
| [runbook.md](docs/runbook.md) | Deploy, backup, incidents |
| [go-live-checklist.md](docs/go-live-checklist.md) | Pre-production verification |
| [research.md](docs/research.md) | Design history and session notes |

---

## Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| **Python** | 3.12+ | Required for native dev and tests |
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
| `http://127.0.0.1:8000/staff/` | Staff desk UI (issue, return, search, overdue) |

Staff UI login: **`librarian`** / **`changeme`** (dev only).

### 4. Run tests (after deploy path has applied migrations)

```bash
make test                 # full suite (unit + integration + e2e)
make test-unit            # no database
make test-integration     # services + orchestrator + DB
make test-e2e             # HTTP journeys + staff UI
make phase7               # concurrency, idempotency, SLO baselines
```

For native tests, Postgres must be running and `DATABASE_URL` in `.env` must match the test database.

### 5. Tear down (dev only)

```bash
make deploy-destroy DESTROY_YES=1    # Docker: stop stack, wipe SQL, remove volumes
make destroy-native DESTROY_YES=1  # Native: wipe data, schema, and database
```

---

## Environment variables

Copy [`.env.example`](.env.example) to `.env`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `APP_ENV` | `development` | Runtime environment |
| `APP_DEBUG` | `true` | Debug mode |
| `APP_SECRET_KEY` | `change-me-in-production` | JWT signing — **change in production** |
| `DATABASE_URL` | `postgresql+psycopg://lms:lms@localhost:5432/lms` | SQLAlchemy URL (native) |
| `JWT_ALGORITHM` | `HS256` | Token algorithm |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `480` | Token lifetime |
| `LIBRARY_TIMEZONE` | `Asia/Kolkata` | Library-local dates |
| `CORS_ORIGINS` | `*` | Comma-separated origins (dev) |

Docker Compose overrides `DATABASE_URL` to point at the `db` service. Optional ports: `LMS_DB_PORT`, `LMS_API_PORT`.

---

## Authentication (JWT)

All `/api/v1/*` endpoints require a **Bearer JWT** except `GET /health` and `POST /api/v1/auth/token`.

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/auth/token \
  -d "username=librarian&password=changeme"

curl -H "Authorization: Bearer <access_token>" \
  http://127.0.0.1:8000/api/v1/reference/patron-types
```

Default users (created by `make seed` / `SEED=1`):

| Username | Role | Password (dev) |
|----------|------|----------------|
| `admin` | ADMIN | `changeme` |
| `librarian` | LIBRARIAN | `changeme` |
| `patron` | PATRON | `changeme` |

In Swagger (`/docs`), use **Authorize** with the raw `access_token` (no `Bearer ` prefix).

---

## Build & deploy reference

| Target | Command | Purpose |
|--------|---------|---------|
| Install (native dev) | `make install` | venv + editable install with dev tools |
| CI (no Docker) | `make ci-native` | lint + test |
| CI parity | `make ci` | lint + test + Docker build |
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

| Layer | Path | Marker |
|-------|------|--------|
| Unit | `tests/unit/` | `@pytest.mark.unit` |
| Integration | `tests/integration/` | `@pytest.mark.integration` |
| E2E | `tests/e2e/` | `@pytest.mark.e2e` |
| Hardening | `tests/hardening/` | `@pytest.mark.hardening` |
| Performance | `tests/performance/` | `@pytest.mark.performance` |

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
  api/           # FastAPI app, auth, workflow coordinators
  reference/     # Patrons, types, class sections
  catalog/       # Bibliographic records, holdings
  loan/          # Circulation, orchestrator, fulfillment
  staff/         # Static desk UI (/staff/)
alembic/         # Database migrations
scripts/         # Deploy, seed, SQL helpers
tests/           # unit, integration, e2e, hardening, performance
docs/            # MVP spec, domain models, runbook
```

**CI:** [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on push/PR to `main` (`make ci-native`).

---

## API surface (MVP)

| Prefix | Domain |
|--------|--------|
| `/api/v1/auth` | JWT token and current user |
| `/api/v1/reference` | Patron types, class sections, patrons |
| `/api/v1/catalog` | Records, holdings, search |
| `/api/v1/loan` | Checkouts, returns, overdue, rules |
| `/api/v1/workflows` | WF-01 issue, WF-02 return (desk + delivery/pick-up) |
| `/staff/` | Staff browser UI |

---

## Production notes

- Set a strong `APP_SECRET_KEY` and change all default passwords before go-live.
- Follow [go-live-checklist.md](docs/go-live-checklist.md) and [runbook.md](docs/runbook.md).
- Run `make phase7` as the hardening gate before production cutover.
