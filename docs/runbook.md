# Operations runbook — LMS-AI MVP

Operational procedures for deploying, backing up, and recovering the LMS-AI K‑12 Library Management MVP.

**Scope:** single-school modular monolith (`src/lms/`). **Authority:** [MVP.md §13](MVP.md), [plan-mvp.md Phase 7](plan-mvp.md).

---

## 1. Prerequisites

| Item | Requirement |
|------|-------------|
| Python | 3.12+ |
| Node.js | 24+ (diagram tooling only; see `.nvmrc`) |
| PostgreSQL | 16 |
| Config | `.env` from `.env.example` (`DATABASE_URL`, `JWT_SECRET`, `LIBRARY_TIMEZONE=Asia/Kolkata`) |
| Tooling | `make install`, `make migrate`; `make install-node` for `make diagram` |

Default API users (dev/demo only — **change before production**):

| Username | Role | Default password |
|----------|------|------------------|
| `admin` | ADMIN | `changeme` |
| `librarian` | LIBRARIAN | `changeme` |
| `patron` | PATRON | `changeme` |

Staff desk UI: `http://<host>:8000/staff/`

---

## 2. Deploy

### Docker (recommended for demo)

```bash
cp .env.example .env
make deploy-local          # db + api + migrations
make deploy-local SEED=1   # include sample data
make deploy-local-logs     # tail logs
```

### Native (local Postgres)

```bash
cp .env.example .env   # set DATABASE_URL
make setup-native SEED=1
make run-dev           # or make deploy-native
```

**Verify after deploy:**

```bash
curl -s http://127.0.0.1:8000/health
# {"status":"ok"}
```

Run smoke tests: `make test-e2e`

---

## 3. Database migrations

| Action | Command |
|--------|---------|
| Apply pending migrations | `make migrate` |
| View current revision | `.venv/bin/alembic current` |
| Generate new migration | `.venv/bin/alembic revision -m "description"` |

### Migration rollback policy (MVP)

1. **Production:** prefer **forward-only** migrations. Fix data/schema with a new Alembic revision rather than `alembic downgrade`, unless the downgrade was tested in staging.
2. **Before cutover:** take a full backup (§4). Run `alembic upgrade head` on a staging copy first.
3. **Failed migration:** stop traffic, restore backup to pre-migration snapshot, investigate, ship a corrective forward migration.
4. **Never** run `make destroy-schema` or `destroy-all` against production.

Alembic history lives in `alembic/versions/`. Domain DDL reference: `scripts/sql/001_domain_ddl.sql`.

---

## 4. Backup and restore

### Backup (PostgreSQL)

```bash
# Full database dump
pg_dump "$DATABASE_URL" -Fc -f "lms-backup-$(date +%Y%m%d-%H%M).dump"

# Schema + data SQL (portable)
pg_dump "$DATABASE_URL" -f "lms-backup-$(date +%Y%m%d).sql"
```

**Recommended cadence:** daily automated backup; retain 30 days for MVP pilot.

### Restore

```bash
# From custom format
pg_restore -d "$DATABASE_URL" --clean --if-exists lms-backup-YYYYMMDD.dump

# From SQL
psql "$DATABASE_URL" -f lms-backup-YYYYMMDD.sql
```

After restore: confirm `alembic current` matches expected revision; run `make test-e2e` against restored instance.

---

## 5. Sample / seed data

| Command | Purpose |
|---------|---------|
| `make seed` | Idempotent Python seed (`scripts/seed_sample_data.py`) |
| `make seed-sql` | SQL seed (`scripts/sql/002_sample_data.sql`) |

Seed includes patron types, loan rules, published catalogs, holdings, and demo loans (including one overdue).

**Teardown (non-production only):**

| Command | Effect |
|---------|---------|
| `make destroy-data` | Remove seed rows |
| `make destroy-schema` | Drop all LMS tables |
| `make destroy-all` | Data + schema + recreate DB |
| `make deploy-destroy` | Stop Docker stack + wipe volumes |

Use `DESTROY_YES=1` to skip confirmation prompts.

---

## 6. Hardening verification (Phase 7)

Before go-live, run:

```bash
make phase7          # hardening + performance SLO tests
make ci-native       # lint + full test suite
```

See [go-live-checklist.md](go-live-checklist.md) for criterion-by-criterion sign-off.

---

## 7. Observability

| Signal | Location |
|--------|----------|
| Health | `GET /health` |
| Correlation id | Response header `X-Correlation-Id` (MVP.md §13.5) |
| API docs | `GET /docs` (Swagger; JWT via Authorize) |
| Logs | Structured stdout (structlog); aggregate at deploy layer |

**Minimum production setup:** ship logs to your platform (CloudWatch, Loki, etc.); alert on health check failures and 5xx rate.

---

## 8. Incident response (circulation)

| Symptom | Likely cause | Action |
|---------|--------------|--------|
| Duplicate loan on same copy | Race without lock (should not happen) | Check partial unique index on open loans; run `make test-hardening` |
| Checkout 422 “not available” | Holding already on loan | Verify open loan; use return workflow |
| Idempotency 409 | Same key, different payload | Client must use new key or replay exact payload |
| 401 on all APIs | Expired/missing JWT | Re-login via `POST /api/v1/auth/token` |

**Mistaken issue at desk:** use WF-01 cancel — `POST /api/v1/workflows/issue/cancel` with `Idempotency-Key`.

---

## 9. Security before production

- [ ] Change all default `api_users` passwords
- [ ] Set strong `JWT_SECRET` in `.env`
- [ ] Disable `APP_DEBUG=true`
- [ ] Restrict network access to PostgreSQL
- [ ] HTTPS termination at reverse proxy
- [ ] Review RBAC matrix (MVP.md §13.4)

---

## 10. Related documents

| Document | Role |
|----------|------|
| [go-live-checklist.md](go-live-checklist.md) | G1–G10 sign-off |
| [plan-mvp.md](plan-mvp.md) | Phase plan |
| [MVP.md §13](MVP.md) | SLOs, idempotency, RBAC |
| [Makefile](../Makefile) | Local commands |
