# Plan — LMS-AI MVP Implementation

Execution plan for the LMS-AI K‑12 Library Management MVP.

**Scope authority:** [MVP.md](MVP.md) §1–§6, §2.1–§2.2 (staff workflows + agent desk), §8–§14. **Domain rules:** [reference.md](reference.md), [catalog.md](catalog.md), [loan.md](loan.md). **Agent governance:** [research.md §15](research.md) (IMDA + Twelve-Factor).

**Out of scope (do not implement):** guardian portals, fines ledger, bulk class issue, renewals, procurement integration, full OPAC polish (MVP.md §1, ADR-011).

---

## 0. Implementation status

| Phase | Status | Notes |
|-------|--------|-------|
| 0 Foundation | **Done** | JWT + `api_users`, idempotency, CI, module boundaries (ADR-024) |
| 1 Reference | **Done** | REST + services under `/api/v1/reference` |
| 2 Loan policy | **Done** | `LoanRuleSet`, `PolicyResolver` |
| 3 Catalog | **Done** | Draft/publish/holdings under `/api/v1/catalog` |
| 4 Circulation | **Done** | `CirculationOrchestrator`, ports, partial unique index |
| 5 Queries | **Done** | Lendable search, open/overdue with display labels; G1 E2E |
| **5A Workflows** | **Done** | WF-01, WF-02 + rollback/name lookup |
| **5B Fulfillment** | **Done** | Delivery/pick-up in MVP scope (MVP.md §5.1) |
| 6 Staff UI | **Done** | Issue/return wizards at `/staff/` |
| 7 Hardening | **Done** | Concurrency, idempotency, SLO tests; [runbook.md](runbook.md), [go-live-checklist.md](go-live-checklist.md) |
| **8 Agent desk** | **Done** | Guided flows + patron desk; LiteLLM Router gateway; Postgres spend + staff cost UI; governance hardening (E27); `make test-agent` (33) |
| **9 Reporting** | **Done** | Dashboard + custom reports (JSON/CSV); `src/lms/reporting/`; staff **Dashboard** panel; `HoldingStatus` DAMAGED/LOST; **17** tests (E29) |

---

## 1. Goal and success criteria

### 1.1 Product goal

Deliver a **coherent circulation slice**: register patrons → configure loan rules → catalog and accession books → checkout/return → staff search and overdue visibility (MVP.md §2 steps 1–8), plus **staff desk workflows** for search/issue and return with optional **delivery/pick-up** (MVP.md §2.1).

### 1.2 MVP done when

| # | Criterion | Verify |
|---|-----------|--------|
| **G1** | Journey steps 1–8 work end-to-end via API (domain + workflow APIs) | E2E: patron + type + rule → publish catalog + holding → checkout → return → search + overdue |
| **G2** | Circulation invariants hold under concurrency | Two simultaneous checkouts on same `holdingId` → exactly one succeeds (REQ-24, MVP.md §13.2) |
| **G3** | Idempotent checkout/return | Same `Idempotency-Key` replay → same outcome, no duplicate loan (MVP.md §13.3) |
| **G4** | RBAC + JWT enforced | Bearer JWT required on domain APIs; unauthorized roles rejected (REQ-21, REQ-30, MVP.md §13.4) |
| **G5** | SLO baselines met on seed data at §13.6 scale | p95 checkout/return ≤ 1200 ms; staff search ≤ 1500 ms (MVP.md §13.1) |
| **G6** | REQ-01 … REQ-30 mapped to shipped handlers/APIs | Traceability checklist §5 complete |
| **G7** | WF-01 desk issue via workflow API | E2E: patron lookup → search → select holding → commit → open loan (REQ-26) |
| **G8** | WF-02 desk return via workflow API | E2E: barcode → return → holding `AVAILABLE` (REQ-27) |
| **G9** | Delivery issue + pick-up return paths | E2E: fulfillment states + custody-aligned loan close (REQ-28, ADR-023) |
| **G10** | Rule preview returns all violations | Unit/integration: blocked patron + unavailable holding → 2+ `rule_id`s (REQ-29) |
| **G11** | Conversational circulation desk with HITL | E2E: guided issue, issued-books inquiry, return, catalog — approval card → commit (REQ-31) |
| **G12** | Agentic fulfillment follow-up with HITL | E2E: delivery issue → agent proposes transition → confirm → `COMPLETED` / in-transit (REQ-32) |
| **G13** | IMDA agent governance charter + Twelve-Factor ops complete | Charter signed; Langfuse audit; config in env; tool allowlist; adversarial tests pass (REQ-34) |

**Note:** G1–G10 gate **Phases 0–7** (wizard + workflow APIs). G11–G13 gate **Phase 8** (agent channel). G6 extends to REQ-34 when Phase 8 ships.

---

## 2. Principles (non-negotiable)

| Principle | Source | Rule |
|-----------|--------|------|
| Modular monolith | ADR-001, ADR-012 | Three modules in one deployable; no cross-module repository calls |
| Circulation kernel | ADR-002 | Only `CirculationOrchestrator` coordinates cross-context writes |
| Ports, not direct DB | ADR-004 | `PatronEligibilityPort`, `HoldingLendabilityPort` at checkout/return |
| Command/query split | ADR-003, ADR-015 | Writes via command handlers; reads via query handlers |
| Fail closed | ADR-005, MVP.md §6 | Unmapped `PatronType` → `LoanRuleSet` rejects checkout |
| Strong consistency | ADR-006, MVP.md §13.2 | Single transaction + row lock on `Holding` for circulation |
| Scope guardrail | ADR-011 | Defer MVP.md §1 out-of-scope; no feature flags on circulation invariants (ADR-020) |
| Idempotency | ADR-017 | `CheckoutHolding` / `ReturnHolding` require `Idempotency-Key` |
| Audit / correlation | ADR-018, MVP.md §13.5 | Correlation id and audit metadata on write operations |
| Workflow coordinators | ADR-021 | Desk workflows compose queries + orchestrator; no cross-context write bypass |
| Custody-aligned circulation | ADR-023 | Loan timestamps follow library custody; pick-up return is two-phase |
| Agent never owns circulation writes | ADR-025, ADR-027 | Tools → workflow services only; HITL before writes |
| PII masking for hosted LLM | ADR-026 | Pseudonyms in prompts; IDs in server session |
| Hosted LLM (no local inference) | ADR-028 | LiteLLM multi-provider; Groq default; optional chain/fallback |

---

## 3. Locked technology decisions

| ID | Decision | Locked choice |
|----|----------|---------------|
| **D1** | Runtime / language | **Python 3.12+** — `src/lms/` modular monolith, FastAPI |
| **D2** | Database | **PostgreSQL 16** — Alembic migrations, row locks, partial unique indexes (ADR-013) |
| **D3** | Auth | **JWT** with roles `ADMIN` / `LIBRARIAN` / `PATRON` (REQ-21) |
| **D4** | Self-checkout | **Librarian-only** for MVP; `PATRON` read-only ([research.md](research.md) OQ-1) |
| **D5** | Class/section | Structured **`ClassSection`** + academic year (REQ-06) |
| **D6** | Library timezone | **`Asia/Kolkata`** — store UTC, compare overdue in policy TZ (REQ-20) |
| **D7** | Primary LLM | **LiteLLM** — default Groq `llama-3.3-70b-versatile`; configurable via `LLM_PROVIDER` |
| **D8** | LLM providers / fallback | **Multi-provider** — `LLM_PROVIDERS` chain (Groq, OpenAI, Anthropic, Together, Hugging Face); legacy `LLM_FALLBACK_*` when chain unset |
| **D9** | Agent stack | **LangGraph** (SOP graph) + **LiteLLM** (routing) + **Langfuse** (observability) |

---

## 4. Implementation phases

Phases follow [MVP.md](MVP.md) §2 journey. Each phase ends with **verify** checks — do not start the next phase until they pass.

### Phase 0 — Foundation ✅ Done

**Goal:** Runnable skeleton with CI, DB migrations, module boundaries, JWT authentication.

**Python project layout** (locked D1–D6):

```
src/lms/
  main.py                 # uvicorn entry
  config.py               # pydantic-settings (DB, JWT, LIBRARY_TIMEZONE)
  api/                    # FastAPI app, middleware, deps, errors, health
  shared/                 # db session, auth/jwt, idempotency, logging, time
  reference/              # domain / application / infrastructure / api
  catalog/
  loan/
    application/circulation_orchestrator.py
    domain/ports.py
alembic/                  # migrations (ADR-014)
tests/                    # unit, integration, e2e
pyproject.toml            # hatchling, ruff, pytest, import-linter
docker-compose.yml        # PostgreSQL 16
.env.example
```

| Task | Deliverable | REQ / ADR |
|------|-------------|-----------|
| Repo layout: `reference/`, `catalog/`, `loan/`, `shared/` | Module folders; no cross-import violations | REQ-01, ADR-001 |
| PostgreSQL + migration tool | Empty schema + migration pipeline | ADR-013, ADR-014 |
| API shell: health, correlation id, error model | `X-Correlation-Id`; flat `{code, message, retriable, details}` envelope | MVP.md §10.5, §13.5 |
| JWT auth: `api_users` table (migration `003`) | Bcrypt passwords; seed users via `ensure_default_api_users` | REQ-30, ADR-024 |
| `POST /api/v1/auth/token`, `GET /api/v1/auth/me` | OAuth2 password flow; Bearer JWT on domain APIs | REQ-30 |
| `domain_api_router` + `HTTPBearer` / Swagger `BearerJWT` | All `/api/v1/reference|catalog|loan` require token | ADR-024 |
| Auth middleware: role extraction | `ADMIN`, `LIBRARIAN`, `PATRON` on request context | REQ-21, ADR-010 |
| CI: unit + integration harness; migration on CI DB | Green pipeline on empty app | MVP.md §10.6 |
| Idempotency store | `idempotency_key`, actor, payload hash, response, `expires_at` | ADR-017, MVP.md §13.3 |

**Verify (regression):** `GET /health` → 200; migration applies cleanly; CI green; module boundaries enforced; unauthenticated domain call → 401.

---

### Phase 1 — Reference domain ✅ Done

**Goal:** Patron master data and eligibility signals (journey step 1).

| Task | Handler / API | REQ |
|------|---------------|-----|
| Schema: `Patron`, `PatronType`, `ClassSection`, `PatronBlock` | Per [reference.md](reference.md) §6 | REQ-03–06 |
| `RegisterPatron`, `UpdatePatron` | Command handlers + REST | REQ-03 |
| `CreatePatronType`, `UpdatePatronType` | Optional `loanRuleSetId` FK | REQ-04, REQ-16 |
| `CreateClassSection`, `AssignPatronToClassSection` | Structured class link | REQ-06 |
| `SuspendPatron`, `ExitPatron`, `SetPatronBlock` | Exit may require zero open loans (stub until Phase 4) | REQ-05 |
| `GetPatronById`, `GetPatronByExternalRef`, `GetPatronByCardBarcode` | Desk lookup queries | Desk workflow |
| Domain rules REF-P*, REF-B*, REF-T*, REF-C* | Aggregate validators | reference.md §5 |

**Verify (regression):** Register student with `PatronType` + `ClassSection`; suspend/block rejected at domain layer; barcode lookup returns patron; audit fields populated (MVP.md §13.5).

---

### Phase 2 — Loan policy ✅ Done

**Goal:** Configurable limits before circulation (journey steps 2–3).

| Task | Handler / API | REQ |
|------|---------------|-----|
| Schema: `LoanRuleSet`, `Loan` (structure only) | `maxActiveLoans`, `loanPeriodDays` | REQ-12, REQ-23 |
| `ConfigureLoanRuleSet`, `UpdateLoanRuleSet` | Admin API | REQ-12 |
| `PolicyResolver`: `PatronType` → `LoanRuleSet`, compute `dueDate` | Fail closed if unmapped | REQ-16, ADR-005 |
| `MapPatronTypeToLoanRuleSet` | Via `UpdatePatronType` or dedicated command | MVP.md §2 step 2 |

**Verify (regression):** Unmapped type → resolver error; mapped type → correct `dueDate` for given `loanPeriodDays`.

---

### Phase 3 — Catalog domain ✅ Done

**Goal:** Bibliographic records and lendable holdings (journey steps 4–5).

| Task | Handler / API | REQ |
|------|---------------|-----|
| Schema: `Catalog`, `Holding` | `DRAFT`/`PUBLISHED`/`SUPPRESSED`; `AVAILABLE`/`ON_LOAN`/`WITHDRAWN` | REQ-07–09, REQ-11 |
| `CreateCatalogDraft`, `UpdateCatalogMetadata` | title, language, optional ISBN, tags | REQ-07 |
| `PublishCatalog`, `SuppressCatalog` | Publish guards (CAT-*) | REQ-08 |
| `AddHoldingToCatalog`, `WithdrawHolding` | barcode + accession unique per tenant | REQ-09, REQ-11 |
| `HoldingLendabilityPort` adapter | Published catalog + `AVAILABLE` holding | REQ-17 |
| Indexes: barcode, accession, catalog status | Per MVP.md §10.4 | ADR-013 |

**Verify (regression):** Unpublished catalog holding not lendable; withdrawn holding rejected; duplicate barcode fails.

---

### Phase 4 — Circulation kernel (critical path) ✅ Done

**Goal:** Checkout and return with cross-context integrity (journey steps 6–7).

| Task | Component | REQ / ADR |
|------|-----------|-----------|
| `PatronEligibilityPort` adapter | ACTIVE, no block, open-loan count vs `maxActiveLoans` | REQ-18 |
| `CirculationOrchestrator.checkout` | Transaction: lock holding → ports → policy → create `Loan` → `ON_LOAN` | REQ-13, ADR-002, MVP.md §13.2 |
| `CirculationOrchestrator.return` | Close loan → `AVAILABLE` | REQ-14 |
| Partial unique index: one open loan per `holding_id` | DB constraint | REQ-24 |
| Idempotency on checkout/return | `Idempotency-Key` header | ADR-017, MVP.md §13.3 |
| Store `loanRuleSetId` on `Loan` at checkout | Policy audit | REQ-23 |
| Domain event records (sync; no bus required) | `LoanCheckedOut`, `LoanReturned` | ADR-009, MVP.md §13.5 |

**Consistency pattern (MVP.md §13.2):**

1. Start one database transaction.
2. Acquire lock on target `Holding` row.
3. Validate lendability and patron eligibility via ports.
4. Apply domain transition (`Loan` open/close + `Holding` status).
5. Persist and commit atomically.
6. Rely on partial unique index as final safety net.

**Verify (regression):**

- Happy path: checkout → holding `ON_LOAN`; return → `AVAILABLE`, `returnedAt` set.
- Reject: blocked patron, max loans exceeded, unpublished catalog, non-available holding.
- Concurrency: parallel checkout same holding → one winner.
- Idempotency: duplicate key → identical response, single loan.

---

### Phase 5 — Queries and staff operations ✅ Done

**Goal:** Discovery and operational visibility (journey step 8).

| Task | Handler / API | REQ | Status |
|------|---------------|-----|--------|
| `SearchCatalogStaff`, `ListHoldings` | Title/ISBN/barcode filters | REQ-10, REQ-25 | **Done** |
| `ListOpenLoansByPatron` | Join labels from Reference/Catalog in read layer | REQ-15, REQ-19 | **Done** |
| `ListOverdueLoans` | Open ∧ `today > dueDate` in library TZ (D6) | REQ-15, REQ-20 | **Done** |
| RBAC + JWT on all endpoints | Per MVP.md §13.4, ADR-024 | REQ-21, REQ-30 | **Done** |
| Staff search filter `PUBLISHED` + lendable holdings view | Issue UI query enhancement | REQ-10 | **Done** |
| Full G1 E2E incl. search + overdue in one script | `test_mvp_journey_includes_search_and_overdue` | REQ-02 | **Done** |

**Verify:** Overdue list correct across timezone boundary; staff search p95 within MVP.md §13.1 on seed data at §13.6 scale.

---

### Phase 5A — Staff desk workflows ✅ Done

**Goal:** WF-01 and WF-02 desk paths per [MVP.md §2.1](MVP.md).

| Task | Deliverable | REQ |
|------|-------------|-----|
| `IssueEligibilityValidator` | Composes ports → `ValidationReport` | REQ-29 |
| `SearchAndIssueWorkflow` | Preview patron, search, list lendable copies, validate, commit | REQ-26 |
| `ReturnBookWorkflow` | Resolve by barcode, preview, desk return | REQ-27 |
| Workflow router `src/lms/api/workflows/` | `POST /api/v1/workflows/issue/start`, `.../commit`, `.../return/...` | REQ-26, REQ-27 |
| Catalog query enhancement | Lendable catalog search / AVAILABLE-only copy list | REQ-10 |
| E2E `tests/e2e/test_workflow_issue_return.py` | G7, G8 | REQ-02 |

**Key files to add:**

```
src/lms/loan/application/workflows/search_and_issue.py
src/lms/loan/application/workflows/return_book.py
src/lms/loan/domain/validation.py
src/lms/api/workflows/router.py
```

**Verify:** Librarian JWT → full desk issue/return via workflow APIs; `ValidationReport` lists named `rule_id`s on failure. Orchestrator contract unchanged.

---

### Phase 5B — Fulfillment (delivery / pick-up)

**Goal:** Optional fulfillment when patron opts for delivery or pick-up (MVP.md §5.1).

| Task | Deliverable | REQ |
|------|-------------|-----|
| Schema `circulation_fulfillments` | Alembic migration `004` | REQ-28 |
| `CirculationFulfillment` aggregate + service | State machine: REQUESTED → READY → IN_TRANSIT → COMPLETED | REQ-28 |
| Extend WF-01 commit | `mode != DESK` → create/update fulfillment after checkout | REQ-28 |
| `InitiateReturnPickup` + `ConfirmReturnReceived` | Two-phase pick-up return (ADR-023) | REQ-27 |
| E2E fulfillment paths | G9 | REQ-28 |

**Verify:** Delivery issue completes fulfillment `COMPLETED` with open loan; pick-up return closes loan only on `ConfirmReturnReceived`.

---

### Phase 6 — Staff UI ✅ Done

**Goal:** Minimum desk-usable UI; API-first if UI slips. Consumes **workflow APIs** (Phase 5A/5B), not raw domain checkout URLs.

| Screen | Actions |
|--------|---------|
| Patron lookup | Scan card / search by admission no. |
| **Issue wizard** | Patron scan → catalog search → copy select → fulfillment choice (desk / delivery / pick-up) |
| **Return wizard** | Barcode scan → desk return or schedule pick-up collection |
| Catalog search | Find title, list holdings |
| Overdue list | Operational report |
| Admin | Patron types, loan rules, class sections |

**Verify:** Librarian completes G1 + G7/G8 journey without raw domain API calls.

---

### Phase 7 — Hardening and go-live ✅ Done

**Goal:** Production readiness per MVP.md §13 and §10.6.

| Task | Source | Status |
|------|--------|--------|
| Load test at §13.6 baselines | §13.6 | **Done** — `tests/performance/test_slo_baselines.py` |
| Lock-contention and idempotency regression suite | §13.2, §13.3 | **Done** — `tests/hardening/` |
| Security hardening (headers, rate limits, error disclosure) | MVP.md §13.7 | **Done** — `api/security_middleware.py`, `tests/hardening/test_security.py` |
| Seed script: patron types, rules, sample catalog | §10.6 | **Done** — `make seed` (~1,614 domain rows; demo + bulk K-12) |
| Runbook: backup, migration rollback policy | §10.6 | **Done** — [runbook.md](runbook.md) |
| Go-live checklist sign-off | §1.2 G1–G10 | **Done** — [go-live-checklist.md](go-live-checklist.md) |

**Verify:** `make phase7` — all G1–G10 criteria pass; `pytest tests/hardening/test_security.py` for §13.7 controls.

---

### Phase 8 — Agent desk (conversational circulation + agentic fulfillment)

**Goal:** Question-driven WF-01/WF-02 and guided desk flows (MVP.md §2.2) without changing the circulation kernel. Governed per IMDA MGF v1.5 + Twelve-Factor App ([research.md §15](research.md)).

**Prerequisites:** Phases 5A/5B/6 complete; enterprise agent charter drafted; at least one provider API key in non-committed env (e.g. `GROQ_API_KEY`).

| Task | Deliverable | REQ |
|------|-------------|-----|
| Enterprise agent charter | Identity, SOP, HITL thresholds, restricted actions | REQ-34 |
| Tool adapters | Typed wrappers over `SearchAndIssueWorkflow`, `FulfillmentService` (no ORM in agent module) | REQ-31, REQ-32 |
| PII session map | Pseudonymizer + server-side slot state; redaction for Langfuse | REQ-33 |
| LangGraph SOP graph | Fixed edges: patron → search → validate → HITL commit → fulfillment subgraph | REQ-31, REQ-34 |
| Governance node + HITL | `_run_tool` allowlist; `pending_approval` + `/resume` before writes | REQ-27, REQ-34 |
| LiteLLM routing | Multi-provider primary + chain + fallback (`llm.py`) | REQ-34, ADR-028 |
| LLM intent prompt | All workflows/actions documented (`llm_intent_prompt.py`) | REQ-31 |
| Guided desk flows | Issue, return, catalog, patron lookup, patron-at-desk loan inquiry | REQ-31, REQ-32 |
| Langfuse integration | Traces with `agent_id`, `thread_id`, redacted tool args | REQ-34 |
| Agent API | `POST /api/v1/agent/issue/sessions`, `.../message`, `.../resume`, session GET | REQ-31 |
| Staff chat UI | Chat + approval cards; transparency copy; wizard remains available | REQ-31 |
| Staff messages module | `messages.py` — intent-aware, query-echo desk copy; coordinator/tools import only | REQ-31 |
| Tests | Tool unit tests (no LLM); agent E2E with mocked LLM; intent/message regression | G11–G13 |
| Docs / runbook | MVP §2.2, §13.8; runbook §10; go-live G11–G13 | REQ-34 |

**Out of scope for Phase 8:**

- Local LLM / Ollama / vLLM on school hardware (ADR-028)
- Groq Compound / HF remote MCP for circulation tools
- Replacing wizard APIs or G7–G10 regression tests

**Verify:**

- `make test-agent` (or `make phase8`) — **32** tests with `AGENT_MOCK_LLM=true` in CI
- `AGENT_ISSUE_ENABLED=true` → librarian completes desk/delivery issue via chat with explicit approval; barcode selection and issue cancel with HITL
- With agent disabled, G1–G10 unchanged
- Langfuse trace shows redacted args + HITL events for every write (**G13 — wired in `tracing.py`; charter sign-off pending**)
- Charter signed by use case owner + security (**G13 — operational**)

**Implementation notes (shipped vs pending):**

| Area | Status |
|------|--------|
| Tool allowlist + `IssueTools` | **Done** — read/write sets in `tools.py`; `_run_tool` enforcement |
| `select_barcode` / `cancel_issue` | **Done** — read barcode via `find_lendable_copy_by_barcode`; cancel with HITL |
| Staff AI assist tab | **Done** — `/staff/` chat + approval cards |
| Rule-based intent parser (CI) | **Done** — `AGENT_MOCK_LLM=true` default in tests |
| LiteLLM multi-provider live path | **Done** — `llm.py`; `LLM_PROVIDER` / `LLM_PROVIDERS`; `AGENT_MOCK_LLM=false` |
| Comprehensive LLM intent prompt | **Done** — `llm_intent_prompt.py`; all `IntentAction` values + examples |
| Guided desk flows + patron loan inquiry | **Done** — `test_agent_guided_issue.py`, `test_agent_guided_flows.py` |
| WF-02 return via agent | **Done** — `test_agent_return.py` |
| Catalog-first issue via agent | **Done** — `test_agent_catalog_issue.py` |
| LangGraph SOP graph | **Partial** — compiles; business logic in `IssueAgentCoordinator` |
| Staff desk copy (`messages.py`) | **Done** — centralized plain-language copy; intent-aware guards; CHAT routing |
| Langfuse integration | **Done** — `tracing.py` + `AgentTracing` in coordinator; charter sign-off still pending |
| Twelve-Factor ops baseline | **Done** — config in `Settings`; `make ci-native` gate; structlog stdout; admin via Makefile |
| Governance runtime controls (E27) | **Done** — production config validation; LLM/history redaction; HITL message block; sanitized approval details; audit spans |
| Durable agent session store | **Pending** — in-process MVP; Postgres/Redis for multi-worker |
| Charter sign-off + eval datasets | **Pending** — G13 operational gate |

---

### Phase 9 — Circulation reporting (post-MVP slice) ✅ Done

**Goal:** Staff operational visibility beyond open/overdue lists — dashboard snapshot and ad-hoc reports without changing the circulation kernel.

| Task | Deliverable | Status |
|------|-------------|--------|
| Reporting bounded context | `src/lms/reporting/` — application + infrastructure queries | **Done** |
| Dashboard API | `GET /api/v1/reporting/dashboard` | **Done** |
| Custom reports | `POST /api/v1/reporting/reports/generate` (JSON/CSV); presets endpoint | **Done** |
| Catalog status extension | `HoldingStatus.DAMAGED`, `HoldingStatus.LOST` | **Done** |
| Staff UI | `DashboardPanel` — Administration → Dashboard | **Done** |
| CI / ops | `make ci-ship`; Docker static path fix; `setup-python@v6`; test settings isolation | **Done** (E29) |

**Verify:** `pytest tests/unit/test_reporting_* tests/integration/test_reporting_service.py` → **17**; full suite **211** via `make ci-native`.

---

## 5. REQ traceability checklist

Mark each REQ during Phase 7 with phase and test id.

| Req | Phase | Test focus |
|-----|-------|------------|
| REQ-01 | 0 | Module boundary lint |
| REQ-02 | 4 | E2E journey |
| REQ-03 | 1 | Register/update patron |
| REQ-04 | 1 | Patron types |
| REQ-05 | 1 | Suspend/exit/block |
| REQ-06 | 1 | Class section |
| REQ-07 | 3 | Catalog draft lifecycle |
| REQ-08 | 3 | Publish gate |
| REQ-09 | 3 | Add holding |
| REQ-10 | 5 | Staff search |
| REQ-11 | 3 | Withdraw holding |
| REQ-12 | 2 | Configure `LoanRuleSet` |
| REQ-13 | 4 | Checkout |
| REQ-14 | 4 | Return |
| REQ-15 | 5 | Open/overdue lists |
| REQ-16 | 2 | Type → rule mapping |
| REQ-17 | 3, 4 | Lendability port |
| REQ-18 | 4 | Patron eligibility port |
| REQ-19 | 4, 5 | Loan boundary + read joins |
| REQ-20 | 5 | Derived overdue + TZ |
| REQ-21 | 0–5 | RBAC matrix |
| REQ-22 | 4 | Event records emitted |
| REQ-23 | 2, 4 | Configurable limits + snapshot on loan |
| REQ-24 | 4 | One open loan per holding |
| REQ-25 | 5 | Staff discovery |
| REQ-26 | 5A | WF-01 search + issue workflow |
| REQ-27 | 5A, 5B | WF-02 return + pick-up paths |
| REQ-28 | 5B | CirculationFulfillment |
| REQ-29 | 5A | ValidationReport |
| REQ-30 | 0 | JWT Bearer on domain APIs |
| REQ-31 | 8 | Conversational WF-01 agent |
| REQ-32 | 8 | Agentic fulfillment subgraph |
| REQ-33 | 8 | PII masking / token minimization |
| REQ-34 | 8 | IMDA charter + Langfuse + governance |

---

## 6. Testing strategy

| Layer | Focus |
|-------|--------|
| Unit | Aggregate invariants (REF-*, CAT-*, loan rules); `ValidationReport` |
| Integration | Handler + DB per module |
| Circulation | Orchestrator + ports + transaction + unique index |
| Workflow | Preview vs commit; desk vs fulfillment branches (G7–G10) |
| Fulfillment | State transitions; custody policy with orchestrator (G9) |
| E2E | Full MVP.md §2 journey + workflow APIs |
| Performance | Checkout/return and search at MVP.md §13.6 scale | `make test-performance` |
| Hardening | Concurrency + idempotency regression | `make test-hardening` |
| Security | Headers, rate limits, production config guards, error disclosure | `pytest tests/hardening/test_security.py` |
| Agent (Phase 8) | SOP adherence, HITL gates, tool allowlist, guided flows, issued-books inquiry, multi-provider LLM, governance hardening, mocked-LLM E2E | `make test-agent` → **33**; `pytest tests/agent/` → **59** |
| Reporting (post-MVP slice) | Dashboard snapshot, presets, JSON/CSV generate, staff RBAC | `pytest tests/unit/test_reporting_* tests/integration/test_reporting_service.py` → **17** |

**CI gate (MVP.md §10.6):** no deploy if migration or circulation tests fail; CI also runs `npm audit --audit-level=high`. Agent tests use **mocked LLM** — no live Groq/HF in CI. Full suite: **211** tests via `make ci-native`; optional **`make ci-ship`** for local commit/push after green CI.

---

## 7. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Cross-context coupling | Enforce ports; review against ADR-004 |
| Double checkout | Row lock + partial unique index (MVP.md §13.2) |
| Scope creep | ADR-011; defer to MVP.md §9.3 roadmap |
| Patron lookup missing at desk | Phase 1 barcode/externalRef queries |
| Self-checkout ambiguity | Lock D4 before Phase 4 |
| Overdue TZ errors | Lock D6; test boundary dates in Phase 5 |
| Workflow bypasses orchestrator | ADR-021: workflows only call orchestrator for writes |
| Pick-up return closes loan early | ADR-023: two-phase return; tests on open-loan invariant |
| Fulfillment scope creep | Desk path works without fulfillment row (`NOT_REQUIRED`) |
| Agent bypasses orchestrator | ADR-025: tools call workflow services only; import-linter on `agent/` module |
| PII sent to Groq/HF | ADR-026 pseudonymization; document residual risk; charter sign-off |
| Automation bias | ADR-027 mandatory HITL; audit override rate in Langfuse |
| LLM cost / abuse | Rate limits + `AGENT_MAX_TOOL_CALLS_PER_TURN`; feature flag off by default |
| Open-ended ReAct | SOP-bound LangGraph; halt-on-error, no infinite retries |

---

## 8. Post-MVP (do not build now)

Bulk class issue, renewals, fines, guardian/notices, full OPAC, procurement — extend via new commands per [MVP.md](MVP.md) §9.3 without changing the orchestrator contract.

**Shipped post-MVP slice (E29):** basic staff **circulation reporting** (dashboard + JSON/CSV custom reports) in `src/lms/reporting/` — not a replacement for leadership analytics or scheduled exports in §9.3.

---

## 9. Related documents

| Document | Use in plan |
|----------|-------------|
| [MVP.md](MVP.md) | Scope, architecture, ADRs, guardrails, REQ traceability |
| [reference.md](reference.md) | Patron rules, entities |
| [catalog.md](catalog.md) | Catalog/holding rules |
| [loan.md](loan.md) | Loan rules, circulation |
| [research.md](research.md) | Deferred decisions (OQ-1 self-checkout); agent governance §15 (IMDA + Twelve-Factor) |
| [.cursor/skills/imda-agentic-ai-governance/SKILL.md](../.cursor/skills/imda-agentic-ai-governance/SKILL.md) | IMDA MGF v1.5 + Twelve-Factor implementation checklist |
| [library_domain_model_final.md](library_domain_model_final.md) | Cross-domain overview |
