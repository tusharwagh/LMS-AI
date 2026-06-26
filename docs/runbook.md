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

**Code layout:** reusable infrastructure under `src/lms/shared/` (`http/`, `auth/deps`, `llm/`, `observability/`); LMS-specific RBAC and API users under `src/lms/platform/`. See [README.md](../README.md#project-layout) and [research.md §13 E30](research.md#e30--session-i-cont-sharedplatform-code-layout-refactor-jun-2026).

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

**Docker staff UI:** the multi-stage `Dockerfile` copies Vite output from the staff-ui build stage at `/build/static` into `src/lms/staff/static/` (not the source tree). Local dev uses the same destination via `make staff-ui-build`.

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
| `make seed-sql` | SQL seed (`scripts/sql/002_sample_data.sql`) — **demo fixtures only** (~25 rows) |

**Python seed (`make seed`)** loads **~1,614 domain rows**: fixed demo fixtures (desk hints below) plus bulk K-12 patrons, NCERT-style catalogs, holdings (3 copies per bulk title), and loans (closed / open / overdue). Clears the seed UUID namespace on each run, then reloads.

| Entity | ~Count |
|--------|--------|
| Patrons | 405 |
| Catalogs | 204 |
| Holdings | 606 |
| Loans | 353 |
| Class sections | 42 |

Optional sizing: `SEED_MIN_RECORDS=1500` (informational target; bulk constants in `scripts/seed_sample_data.py`).

**Demo desk hints (unchanged):**

| Lookup | Resolves to |
|--------|-------------|
| `LIB-7001` | Arjun Mehta — open loan on `BC-MATH7-001` |
| `LIB-8001` | Rohan Das — overdue loan on `BC-MATH7-002` |
| `BC-PAN-001` | Panchatantra (available) |
| `BC-NEH-001` | Discovery of India (reference, non-circulating) |

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
| `LLM_MAX_PROMPT_CHARS` | `12000` | Structural guardrail — max total prompt characters |
| `LLM_MAX_TOKENS_CAP` | `4096` | Structural guardrail — max `max_tokens` per request |
| `NEMO_GUARDRAILS_ENABLED` | `false` | Enable NVIDIA NeMo Guardrails input/output rails on `LlmGateway.complete()` |
| `NEMO_GUARDRAILS_CONFIG_PATH` | `guardrails/nemoguards` | Directory with `config.yml` (+ `prompts.yaml` when needed) |
| `NVIDIA_API_KEY` | — | Required for **nemoguards** profile (content safety, topic control, jailbreak NIM) |
| `LLM_CACHE_ENABLED` | `true` | LiteLLM response cache (`LLM_CACHE_TYPE`) |
| `LLM_CACHE_TYPE` | `local` | `local` or `redis` |
| `LLM_CACHE_TTL_SECONDS` | `600` | Cache entry lifetime |
| `LLM_CACHE_REDIS_URL` | — | Redis URL when `LLM_CACHE_TYPE=redis` |
| `LLM_RATE_LIMIT_ENABLED` | `true` | Router deployment RPM budget |
| `LLM_RATE_LIMIT_MAX` | `120` | Max gateway calls per window |
| `LLM_RATE_LIMIT_WINDOW_SECONDS` | `60` | Rate limit window (converted to RPM) |
| `LLM_PROXY_URL` | — | Optional LiteLLM Proxy pass-through base URL |
| `LLM_PROXY_API_KEY` | — | Optional proxy virtual/master key |
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

**Example — NeMo Guardrails (nemoguards profile):**

```env
NEMO_GUARDRAILS_ENABLED=true
NEMO_GUARDRAILS_CONFIG_PATH=guardrails/nemoguards
NVIDIA_API_KEY=...
# Intent parsing still uses LiteLLM (e.g. GROQ_API_KEY above)
```

Alternative **self-check** profile (OpenAI only for rail LLM calls): `NEMO_GUARDRAILS_CONFIG_PATH=guardrails/self-check` and set `OPENAI_API_KEY`.

Routing implementation: `src/lms/shared/llm/` — `LlmGateway.complete()` runs **structural validation** (`guardrails.py`), optional **NeMo input/output rails** (`nemo_guardrails.py`), then LiteLLM `Router` (or optional `LLM_PROXY_URL` pass-through). Postgres spend in `llm_spend_logs`; query service in `shared/llm/spend_queries.py`. Intent classification prompt: `src/lms/agent/llm_intent_prompt.py`. Langfuse ops check: `scripts/validate_langfuse.py` → `shared/observability/tracing.py`.

**NeMo Guardrails flow (when enabled):** staff/user message → NeMo **input** rails (jailbreak / topic / content safety per config) → LiteLLM completion → NeMo **output** rails → `LLMIntentParser` → coordinator (HITL unchanged). Blocked requests raise `LlmGuardrailError`; intent parser falls back to rule-based parsing on LLM/guardrail failure.

**Install:** package extra `guardrails` (`nemoguardrails>=0.22.0`). Dev/CI: `pip install -e ".[dev]"` (includes `nemoguardrails` in dev deps). Production with rails only: `pip install 'lms-ai[guardrails]'`. Config bundles: `guardrails/nemoguards/` (NVIDIA NIMs), `guardrails/self-check/` (LLM self-check). Docs: [NVIDIA NeMo Guardrails](https://docs.nvidia.com/nemo/guardrails/latest/get-started/installation-guide.html).

**Langfuse SDK 4.x:** dependency pinned `langfuse>=4.0,<5`. Agent audit spans (`turn_span`, `tool_span`, `intent_span`) use `LangfuseTracing` (SDK v4 client). LiteLLM registers `"langfuse"` in success/failure callbacks only when the SDK exposes `langfuse.version` (v2 API); on v4, `setup.py` skips that callback and logs `litellm_langfuse_callback_skipped` — `make validate-langfuse` still validates agent spans.

**Patron lookup (workflows + agent):** `reference/application/patron_query.py` — `parse_patron_query()` accepts patron UUID, **CARD-***, **ADM-***, or partial display name (trailing `?.!,` stripped). WF-01 `IssueStartRequest.patron_query` and `IssueSearchPatronsRequest.query`; return workflow uses the same resolution. Ambiguous name → **409 CONFLICT** with `details.patrons` (wizard) or candidate list in agent chat (**PATRON_N**, card, admission).

**Cost reporting (staff/admin):** `GET /api/v1/llm-spend/logs` (paginated list with optional `from_date`, `to_date`, `purpose`, `model`, `session_id`, `operator_id`) and `GET /api/v1/llm-spend/summary` (aggregates by purpose/model). Requires librarian or admin JWT. Staff desk: **Administration → LLM costs** (`LlmSpendPanel`).

**Circulation reporting (staff):** `GET /api/v1/reporting/dashboard` (holdings by status, active/overdue loans, today’s issues/returns, daily series), `POST /api/v1/reporting/reports/generate` (custom metrics, JSON or CSV), and `GET /api/v1/reporting/reports/presets`. Requires librarian or admin JWT. Staff desk: **Administration → Dashboard** (`DashboardPanel`).

### Twelve-Factor deployment (agent)

Operational baseline aligned with IMDA skill §“12-Factor agent deployment” and [research.md §15.9](research.md).

| Stage | Command / practice |
|-------|-------------------|
| **Build + test** | `make ci-native` — ruff, mypy, import-linter, full pytest (**211** tests; mock LLM) |
| **Ship locally** | `make ci-ship` — runs `ci-native`, prompts for commit message, then `git commit` + `git push` (`scripts/ci_commit_push.sh`) |
| **Release** | Tag deploy with graph/prompt version; set env on target host (never edit code at runtime) |
| **Run** | `make deploy-native` or `make run-dev` — starts Uvicorn only; migrations already applied |
| **Config** | All agent toggles in `.env` / process env — see table above; validate production rejects defaults |
| **Logs** | Aggregate stdout JSON from API process; Langfuse for tool/model audit when keys set |
| **Admin** | Run `make migrate` and `make seed` as release steps — not from agent chat |

**Stateless workers (MVP):** agent session and HITL state live in an **in-process `SessionStore`** (`session.py`). Run **one API worker** per desk deployment; restart clears sessions. Durable Postgres/Redis store is the next production step — see [research.md §15.10](research.md).

**Production startup** (`APP_ENV=production`): rejects default `DATABASE_URL`; when `AGENT_ISSUE_ENABLED=true`, requires `AGENT_MOCK_LLM=false`, at least one LLM provider key, and `LANGFUSE_*` keys.

**Governance behaviors:** LLM intent input redacted; new chat messages blocked while approval pending; HITL `details` on API omit internal UUIDs.

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
| Patron lookup | “Lookup patron”, “Riya Sharma”, “CARD-12345” | `start_patron_lookup`, `provide_patron_lookup`, `select_patron` |
| Cancel guided flow | “cancel”, “never mind” | `decline_continue` |

**Disambiguation:** When patron, catalog copy, or return-loan lookups return multiple rows, the agent lists candidates with business keys (**PATRON_N**, **COPY_N**, **LOAN_N**, plus **CARD-***/**ADM-***/barcode when shown). Staff reply with a key from the list — ambiguity is never a terminal error.

Full action list and LLM examples: `src/lms/agent/llm_intent_prompt.py`. Rule-based fallback: `src/lms/agent/intent_parser.py` (used when `AGENT_MOCK_LLM=true` or LLM unavailable); issued-books partial names via `_parse_issued_books_query()`.

### Staff-facing messages

Librarians see `assistant_message` and approval `summary` from the API — built in `src/lms/agent/messages.py`, not in the UI. Copy is plain desk language (patron names, titles, barcodes). Candidate lists include business keys (**PATRON_N**, **COPY_N**, **LOAN_N**, **CARD-***, **ADM-***) for selection; raw UUIDs must not appear. If responses look technical (UUIDs, tool names, “missing slot”), treat as a defect — see [research.md §13 E21](research.md).

### Pre-enable checklist

- [ ] Enterprise agent charter signed ([research.md §15.2](research.md))
- [ ] Residual risk accepted (student/patron data pseudonymized but sent to hosted LLM provider(s))
- [ ] Langfuse project created; retention policy set
- [ ] `AGENT_ISSUE_ENABLED=true` only on pilot cohort
- [ ] If `NEMO_GUARDRAILS_ENABLED=true`: `NVIDIA_API_KEY` (nemoguards) or `OPENAI_API_KEY` (self-check) set; config path exists under `guardrails/`
- [ ] Wizard workflows (G7–G10) regression-tested with agent flag on

**Validate Langfuse locally** (runs automatically on `make build`; also `make validate-langfuse`):

```bash
make validate-langfuse
```

Expect `auth_ok: True` and a test `turn:validate` / `tool:search_patrons` span in your Langfuse project (agent tracing via SDK v4). US cloud projects must use `https://us.cloud.langfuse.com`, not the default EU host.

### Incident response (agent)

| Symptom | Action |
|---------|--------|
| Runaway LLM spend | Set `AGENT_ISSUE_ENABLED=false`; review Langfuse token metrics |
| Wrong issue after approval | Use agent `"Cancel the issue"` (HITL) or WF-01 cancel API; review HITL audit trace |
| Groq / OpenAI / other provider outage | Agent falls back to next `LLM_PROVIDERS` entry; if all fail, rule parser or 503; use wizard UI at `/staff/` |
| Suspected prompt injection | Disable agent; review Langfuse trace + governance blocks |
| NeMo Guardrails blocking legitimate desk phrases | Review `guardrails/*/prompts.yaml` topic rules; temporarily set `NEMO_GUARDRAILS_ENABLED=false`; check structlog `nemo_guardrails_blocked` events |

---

## 11. Circulation reporting

Staff operational reporting — read-only queries over circulation and catalog data. Module: `src/lms/reporting/` (separate bounded context; no cross-context writes).

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/reporting/dashboard` | Snapshot: holdings by status (incl. **DAMAGED** / **LOST**), active and overdue loans, today’s issues/returns, daily issue/return series (`days` 7–90 or explicit `from_date`/`to_date`) |
| `POST /api/v1/reporting/reports/generate` | Ad-hoc report from selected metrics; **JSON** body response or **CSV** attachment |
| `GET /api/v1/reporting/reports/presets` | Named presets for the report builder |

**RBAC:** librarian or admin JWT only (`require_staff`); patron role receives 403.

**Staff desk:** **Administration → Dashboard** (`DashboardPanel` in `src/lms/staff/ui/`).

**Metrics** (`ReportMetric` enum): `daily_issues`, `daily_returns`, `holdings_by_status`, `total_active_loans`, `overdue_loans`. **Formats:** `json` (default) or `csv` (attachment). **Presets:** `daily_circulation`, `holdings_snapshot`, `loan_health`, `full_dashboard`.

**Examples** (replace `<token>` with a librarian/admin JWT from `POST /api/v1/auth/login`):

```bash
# Dashboard snapshot (last 30 days)
curl -s -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:8000/api/v1/reporting/dashboard?days=30" | jq .

# Dashboard with explicit date range (both from_date and to_date required)
curl -s -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:8000/api/v1/reporting/dashboard?from_date=2026-05-01&to_date=2026-05-31" | jq .

# List built-in report presets
curl -s -H "Authorization: Bearer <token>" \
  "http://127.0.0.1:8000/api/v1/reporting/reports/presets" | jq .

# Generate JSON report (daily issues + returns)
curl -s -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"metrics":["daily_issues","daily_returns"],"from_date":"2026-05-01","to_date":"2026-05-31","format":"json"}' \
  "http://127.0.0.1:8000/api/v1/reporting/reports/generate" | jq .

# Download CSV export
curl -s -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"metrics":["holdings_by_status","total_active_loans"],"from_date":"2026-06-01","to_date":"2026-06-13","format":"csv"}' \
  -o circulation-report.csv \
  "http://127.0.0.1:8000/api/v1/reporting/reports/generate"
```

**Sample dashboard response** (truncated):

```json
{
  "holdings_by_status": {"AVAILABLE": 420, "LOANED": 310, "DAMAGED": 12, "LOST": 4},
  "circulation": {"total_active_loans": 310, "overdue_loans": 18},
  "today": {"issues_today": 5, "returns_today": 3},
  "daily_series": [{"date": "2026-06-12", "issues": 4, "returns": 2}],
  "from_date": "2026-05-14",
  "to_date": "2026-06-13"
}
```

**Verify:**

```bash
make ci-native   # includes 17 reporting tests (RBAC, schemas, integration)
pytest tests/unit/test_reporting_* tests/integration/test_reporting_service.py
```

**Post-MVP extensions** (not shipped): scheduled exports, chart widgets, leadership roll-ups — see [MVP.md §9.3](MVP.md).

---

## 12. Related documents

| Document | Role |
|----------|------|
| [go-live-checklist.md](go-live-checklist.md) | G1–G13 sign-off |
| [plan-mvp.md](plan-mvp.md) | Phase plan (incl. Phase 8) |
| [MVP.md §2.2, §13.8](MVP.md) | Agent desk spec + LLM security |
| [research.md §15](research.md) | IMDA + Twelve-Factor agent governance charter |
| [Makefile](../Makefile) | Local commands |
