# LMS — K-12 Library Management (MVP)

Python modular monolith. Specs: [MVP.md](docs/MVP.md) · Implementation plan: [plan-mvp.md](docs/plan-mvp.md) · All docs: [docs/](docs/).

## Build & local deployment pipeline

| Target | Command | Purpose |
|--------|---------|---------|
| Install (native dev) | `make install` | venv + editable install with dev tools |
| CI (no Docker) | `make ci-native` | lint + test |
| CI parity | `make ci` | lint + test + Docker build |
| **Native deploy** | `make deploy-native` | **No Docker** — venv + migrate + API |
| Native deploy + seed | `make deploy-native SEED=1` | Deploy + demo data |
| Native teardown | `make destroy-native` | Wipe data, schema, database |
| Native setup only | `make setup-native` | install + migrate (no server) |
| Native dev server | `make run-dev` | Uvicorn with reload only |
| Docker deploy | `make deploy-local` | Compose: Postgres + migrate + API |
| Docker teardown | `make deploy-destroy` | Stop stack, wipe SQL, remove volumes |

### Native (no Docker)

Requires **PostgreSQL already running** on your machine. Set `DATABASE_URL` in `.env` (see `.env.example`).

```bash
cp .env.example .env
# Edit DATABASE_URL, e.g. postgresql+psycopg://postgres:postgres@localhost:5432/lms

make deploy-native              # install (if needed), migrate, run API
make deploy-native SEED=1       # + sample data
make destroy-native DESTROY_YES=1   # tear down DB (no Docker)
```

Or step by step:

```bash
make install
make setup-native SEED=1        # migrate + optional seed
make run-dev
```

### Docker

```bash
cp .env.example .env
make deploy-local
make deploy-local SEED=1
make deploy-destroy DESTROY_YES=1
```

**CI:** GitHub Actions workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs on push/PR to `main`.

## Tests

Requires Postgres running and migrations applied (`make migrate`).

```bash
make test                 # all suites
make test-unit            # no database
make test-integration     # services + orchestrator + DB
make test-e2e             # full HTTP journeys
```

| Layer | Path | Marker |
|-------|------|--------|
| Unit | `tests/unit/` | `@pytest.mark.unit` |
| Integration | `tests/integration/` | `@pytest.mark.integration` |
| E2E | `tests/e2e/` | `@pytest.mark.e2e` |

## Schema & sample data (SQL)

- DDL: [scripts/sql/001_domain_ddl.sql](scripts/sql/001_domain_ddl.sql)
- Seed: [scripts/sql/002_sample_data.sql](scripts/sql/002_sample_data.sql)
- Destroy: [scripts/sql/003_destroy_sample_data.sql](scripts/sql/003_destroy_sample_data.sql) · [scripts/sql/004_destroy_schema.sql](scripts/sql/004_destroy_schema.sql)

Or use `make seed` / `make destroy-native`.

Health: `GET http://localhost:8000/health` · Docs: `http://localhost:8000/docs`

## Authentication (JWT)

All `/api/v1/*` endpoints require a **Bearer JWT** except `GET /health` and `POST /api/v1/auth/token`.

1. Obtain a token (OAuth2 password flow):

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/token \
  -d "username=librarian&password=changeme"
```

2. Call APIs with the token:

```bash
curl -H "Authorization: Bearer <access_token>" \
  http://localhost:8000/api/v1/reference/patron-types
```

Default users are created by `make seed` (password **`changeme`** in dev — change in production):

| Username | Role | Typical use |
|----------|------|-------------|
| `admin` | ADMIN | Loan rules, full configuration |
| `librarian` | LIBRARIAN | Desk circulation, catalog, patrons |
| `patron` | PATRON | Reserved for future self-service reads |

Use **Authorize** in Swagger UI (`/docs`) — enter the `access_token` from the login response (no `Bearer ` prefix). Authorization persists across reloads. Token URL for login: `POST /api/v1/auth/token` (expand **auth** → **token**).

Set a strong `APP_SECRET_KEY` in `.env` for production JWT signing.
