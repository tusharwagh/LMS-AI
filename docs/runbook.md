# Operations runbook — LMS-AI MVP

Operational procedures for deploying, backing up, and recovering the LMS-AI K‑12 Library Management MVP.

**Scope:** single-school modular monolith (`src/lms/`). **Authority:** [MVP.md §13](MVP.md), [plan-mvp.md](plan-mvp.md) (Phases 7–8).

---

## 1. Prerequisites

| Item | Requirement |
|------|-------------|
| Python | 3.12+ |
| Node.js | 24+ (diagram tooling only; see `.nvmrc`) |
| PostgreSQL | 16 |
| Config | `.env` from `.env.example` (`DATABASE_URL`, `APP_SECRET_KEY`, `LIBRARY_TIMEZONE=Asia/Kolkata`) |
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
pytest tests/hardening/test_security.py   # security headers, rate limits, error disclosure
```

See [go-live-checklist.md](go-live-checklist.md) for criterion-by-criterion sign-off.

---

## 7. Observability

| Signal | Location |
|--------|----------|
| Health | `GET /health` |
| Correlation id | Response header `X-Correlation-Id` (MVP.md §13.5) |
| Security headers | `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, etc. (MVP.md §13.7) |
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
| 429 on login or API | Rate limit exceeded | Wait for `Retry-After` window; check brute-force / desk automation |

**Mistaken issue at desk:** use WF-01 cancel — `POST /api/v1/workflows/issue/cancel` with `Idempotency-Key`.

---

## 9. Security before production

- [ ] Change all default `api_users` passwords (`admin`, `librarian`, `patron`)
- [ ] Set strong `APP_SECRET_KEY` in `.env` (used to sign JWTs)
- [ ] Set `APP_ENV=production` — startup **rejects** default secret and `CORS_ORIGINS=*`
- [ ] Set `APP_DEBUG=false` — API returns generic validation/500 messages (no stack traces)
- [ ] Set explicit `CORS_ORIGINS` (comma-separated staff UI origins)
- [ ] Enable `SECURITY_HSTS_ENABLED=true` only when HTTPS is terminated in front of the API
- [ ] Keep `RATE_LIMIT_ENABLED=true` (default); tune `AUTH_RATE_LIMIT_*` / `API_RATE_LIMIT_*` if needed
- [ ] Restrict network access to PostgreSQL
- [ ] HTTPS termination at reverse proxy
- [ ] Review RBAC matrix (MVP.md §13.4)
- [ ] Run `pytest tests/hardening/test_security.py` and confirm CI `npm audit` is clean

### Environment variables (security)

| Variable | Default (dev) | Production guidance |
|----------|---------------|---------------------|
| `APP_SECRET_KEY` | `change-me-in-production` | Strong random secret; required change when `APP_ENV=production` |
| `APP_DEBUG` | `true` in `.env.example` | `false` |
| `CORS_ORIGINS` | `*` | Explicit origin list only |
| `SECURITY_HSTS_ENABLED` | `false` | `true` behind HTTPS |
| `RATE_LIMIT_ENABLED` | `true` | Keep enabled |
| `AUTH_RATE_LIMIT_MAX` | `10` | Stricter if under attack |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | `900` | 15 minutes |
| `API_RATE_LIMIT_MAX` | `100` | Adjust for desk load |
| `API_RATE_LIMIT_WINDOW_SECONDS` | `900` | 15 minutes |

---

## 10. Agent desk — LLM and observability (Phase 8)

Conversational WF-01 and agentic fulfillment ([MVP.md §2.2](MVP.md)). **No local LLM** for MVP — hosted Groq primary, optional Hugging Face Inference fallback (ADR-028).

### Environment variables (agent)

| Variable | Default (dev) | Production guidance |
|----------|---------------|---------------------|
| `AGENT_ISSUE_ENABLED` | `false` | Enable only after G11–G13 sign-off |
| `AGENT_MOCK_LLM` | `true` (tests/CI) | Set `false` + `GROQ_API_KEY` for live Groq intent parsing |
| `GROQ_API_KEY` | — | Required when agent enabled with live LLM; never commit |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Pin version; change via LiteLLM config |
| `LLM_MODEL_FAST` | `llama-3.1-8b-instant` | Optional; short clarifications only |
| `LLM_FALLBACK_ENABLED` | `false` | Keep off unless HF fallback tested |
| `HF_TOKEN` | — | Only if fallback enabled |
| `LLM_FALLBACK_MODEL` | — | Pin model id (e.g. `Qwen/Qwen2.5-72B-Instruct`) |
| `LLM_FALLBACK_PROVIDER` | — | **Pin** provider; no `:fastest` in production |
| `AGENT_MAX_TOOL_CALLS_PER_TURN` | `5` | Lower if abuse observed |
| `LANGFUSE_PUBLIC_KEY` | — | Required for agent audit in production |
| `LANGFUSE_SECRET_KEY` | — | Never commit |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Self-hosted if required by school IT |

### Authorized agent tools

Enforced in `IssueAgentCoordinator._run_tool` (`src/lms/agent/tools.py`):

| Class | Tool names |
|-------|------------|
| **Read** | `search_patrons`, `resolve_patron`, `search_lendable`, `select_barcode`, `validate_issue`, `get_fulfillment_status` |
| **Write (HITL)** | `commit_issue`, `cancel_issue`, `transition_fulfillment` |
| **Restricted** | `direct_checkout`, `direct_db`, `admin_api`, `remote_mcp` |

Writes require librarian approval via `pending_approval` and `POST /api/v1/agent/issue/sessions/{id}/resume`.

### Pre-enable checklist

- [ ] Enterprise agent charter signed ([research.md §15.2](research.md))
- [ ] Residual risk accepted (student/patron data pseudonymized but sent to Groq/HF)
- [ ] Langfuse project created; retention policy set
- [ ] `AGENT_ISSUE_ENABLED=true` only on pilot cohort
- [ ] Wizard workflows (G7–G10) regression-tested with agent flag on

### Incident response (agent)

| Symptom | Action |
|---------|--------|
| Runaway LLM spend | Set `AGENT_ISSUE_ENABLED=false`; review Langfuse token metrics |
| Wrong issue after approval | Use agent `"Cancel the issue"` (HITL) or WF-01 cancel API; review HITL audit trace |
| Groq / HF outage | Agent returns 503; fall back to wizard UI at `/staff/` |
| Suspected prompt injection | Disable agent; review Langfuse trace + governance blocks |

---

## 11. Related documents

| Document | Role |
|----------|------|
| [go-live-checklist.md](go-live-checklist.md) | G1–G13 sign-off |
| [plan-mvp.md](plan-mvp.md) | Phase plan (incl. Phase 8) |
| [MVP.md §2.2, §13.8](MVP.md) | Agent desk spec + LLM security |
| [research.md §15](research.md) | IMDA agent governance charter |
| [Makefile](../Makefile) | Local commands |
