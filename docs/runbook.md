# Operations runbook — LMS-AI MVP

Operational procedures for deploying, backing up, and recovering the LMS-AI K‑12 Library Management MVP.

**Scope:** single-school modular monolith (`src/lms/`). **Authority:** [MVP.md §13](MVP.md), [plan-mvp.md](plan-mvp.md) (Phases 7–8).

---

## 1. Prerequisites

| Item | Requirement |
|------|-------------|
| Python | 3.12+ |
| Node.js | 24+ (diagram tooling + staff UI build; see `.nvmrc`) |
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

**Staff UI build:** source in `src/lms/staff/ui/`; Vite output under `src/lms/staff/static/` is **not committed** (see `.gitignore`; only `.gitkeep` is tracked). Always build before deploy or E2E — `make staff-ui-build` runs in CI, Docker, `make setup-native`, and `scripts/deploy-native.sh`.

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

Browser E2E (Playwright): `make test-e2e-playwright` — login, issue wizard, return wizard, agent pending approval, agent HITL approve.

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

Conversational circulation desk ([MVP.md §2.2](MVP.md)): guided issue, return, catalog browse, patron lookup, and **patron-at-desk loan inquiry** (“what books are issued to …?”). **No local LLM** for MVP — hosted providers via **LiteLLM** (ADR-028).

### Environment variables (agent)

| Variable | Default (dev) | Production guidance |
|----------|---------------|---------------------|
| `AGENT_ISSUE_ENABLED` | `false` | Enable only after G11–G13 sign-off |
| `AGENT_MOCK_LLM` | `true` (tests/CI) | Set `false` + at least one provider API key for live intent parsing |
| `LLM_PROVIDER` | `groq` | Primary: `groq`, `openai`, `anthropic`, `together`, `huggingface` |
| `LLM_PROVIDERS` | *(empty)* | Optional chain, e.g. `groq,openai` or `groq:llama-3.3-70b-versatile,openai:gpt-4o-mini` (overrides `LLM_PROVIDER` + legacy fallback) |
| `GROQ_API_KEY` | — | Set if using Groq; never commit |
| `OPENAI_API_KEY` | — | Set if using OpenAI |
| `ANTHROPIC_API_KEY` | — | Set if using Anthropic |
| `TOGETHER_API_KEY` | — | Set if using Together |
| `HF_TOKEN` | — | Hugging Face Inference; also used for legacy `LLM_FALLBACK_*` |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Default model for primary provider |
| `LLM_MODEL_FAST` | `llama-3.1-8b-instant` | Optional; short clarifications only |
| `LLM_FALLBACK_ENABLED` | `false` | Legacy fallback when `LLM_PROVIDERS` unset |
| `LLM_FALLBACK_PROVIDER` | `together` | Pin provider; no `:fastest` in production |
| `LLM_FALLBACK_MODEL` | `Qwen/Qwen2.5-72B-Instruct` | Pin model id |
| `AGENT_MAX_TOOL_CALLS_PER_TURN` | `5` | Lower if abuse observed |
| `LANGFUSE_PUBLIC_KEY` | — | Required for agent audit in production |
| `LANGFUSE_SECRET_KEY` | — | Never commit |
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | Self-hosted if required by school IT |
| `LANGFUSE_BASE_URL` | *(alias)* | Same as `LANGFUSE_HOST` (e.g. `https://us.cloud.langfuse.com`) |

**Example — Groq only:**

```env
AGENT_ISSUE_ENABLED=true
AGENT_MOCK_LLM=false
LLM_PROVIDER=groq
GROQ_API_KEY=...
LLM_MODEL=llama-3.3-70b-versatile
```

**Example — Groq with OpenAI fallback:**

```env
LLM_PROVIDERS=groq,openai
GROQ_API_KEY=...
OPENAI_API_KEY=...
```

Routing implementation: `src/lms/agent/llm.py` (`completion_with_fallback`). Intent classification prompt: `src/lms/agent/llm_intent_prompt.py`.

### Authorized agent tools

Enforced in `IssueAgentCoordinator._run_tool` (`src/lms/agent/tools.py`):

| Class | Tool names |
|-------|------------|
| **Read** | `search_patrons`, `resolve_patron`, `search_lendable`, `search_catalog`, `select_catalog_copy`, `select_patron`, `select_barcode`, `validate_issue`, `get_fulfillment_status`, `lookup_return`, `search_return_loans`, `list_patron_loans_at_desk`, `select_return_loan` |
| **Write (HITL)** | `commit_issue`, `cancel_issue`, `transition_fulfillment`, `commit_desk_return`, `initiate_return_pickup`, `apply_return_selection` |
| **Restricted** | `direct_checkout`, `direct_db`, `admin_api`, `remote_mcp` |

Writes require librarian approval via `pending_approval` and `POST /api/v1/agent/issue/sessions/{id}/resume`.

### Conversational workflows (intent → coordinator)

| Workflow | Staff examples | Key intents |
|----------|----------------|-------------|
| Guided issue | “I want to issue a book”, “science fiction” (after prompts) | `start_issue_to_patron`, `provide_patron_for_issue`, `provide_book_criteria`, `request_commit` |
| One-shot issue | “Issue Harry Potter to Riya, desk pickup” | `request_commit` |
| Patron desk / issued books | “What books are issued to Riya?”, “List open loans for Sharma” | `start_patron_desk`, `provide_patron_for_desk`, `desk_start_*` |
| Return | “Return barcode ABC-123”, “I want to return a book” | `lookup_return`, `start_return`, `request_commit_return` |
| Catalog browse | “Browse catalog”, “mystery novels” | `start_catalog_search`, `provide_catalog_criteria` |
| Patron lookup | “Lookup patron”, “Riya Sharma” | `start_patron_lookup`, `provide_patron_lookup` |
| Cancel guided flow | “cancel”, “never mind” | `decline_continue` |

Full action list and LLM examples: `src/lms/agent/llm_intent_prompt.py`. Rule-based fallback: `src/lms/agent/intent_parser.py` (used when `AGENT_MOCK_LLM=true` or LLM unavailable).

### Staff-facing messages

Librarians see `assistant_message` and approval `summary` from the API — built in `src/lms/agent/messages.py`, not in the UI. Copy is plain desk language (patron names, titles, barcodes); it echoes search queries where relevant and always includes a next action. If responses look technical (UUIDs, tool names, “missing slot”), treat as a defect — see [research.md §13 E21](research.md).

### Pre-enable checklist

- [ ] Enterprise agent charter signed ([research.md §15.2](research.md))
- [ ] Residual risk accepted (student/patron data pseudonymized but sent to hosted LLM provider(s))
- [ ] Langfuse project created; retention policy set
- [ ] `AGENT_ISSUE_ENABLED=true` only on pilot cohort
- [ ] Wizard workflows (G7–G10) regression-tested with agent flag on

**Validate Langfuse locally** (runs automatically on `make build`; also `make validate-langfuse`):

```bash
make validate-langfuse
```

Expect `auth_ok: True` and a test `turn:validate` / `tool:search_patrons` span in your Langfuse project. US cloud projects must use `https://us.cloud.langfuse.com`, not the default EU host.

### Incident response (agent)

| Symptom | Action |
|---------|--------|
| Runaway LLM spend | Set `AGENT_ISSUE_ENABLED=false`; review Langfuse token metrics |
| Wrong issue after approval | Use agent `"Cancel the issue"` (HITL) or WF-01 cancel API; review HITL audit trace |
| Groq / OpenAI / other provider outage | Agent falls back to next `LLM_PROVIDERS` entry; if all fail, rule parser or 503; use wizard UI at `/staff/` |
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
