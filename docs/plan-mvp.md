# Plan — MVP Implementation

Execution plan for the K‑12 Library Management MVP.

**Scope authority:** [MVP.md](MVP.md) §1–§6, §8–§13. **Domain rules:** [reference.md](reference.md), [catalog.md](catalog.md), [loan.md](loan.md).

**Out of scope (do not implement):** guardian portals, fines ledger, bulk class issue, renewals, procurement integration, full OPAC polish (MVP.md §1, ADR-011).

---

## 1. Goal and success criteria

### 1.1 Product goal

Deliver a **coherent circulation slice**: register patrons → configure loan rules → catalog and accession books → checkout/return → staff search and overdue visibility (MVP.md §2 journey steps 1–8).

### 1.2 MVP done when

| # | Criterion | Verify |
|---|-----------|--------|
| **G1** | Journey steps 1–8 work end-to-end via API | Scripted E2E: patron + type + rule → publish catalog + holding → checkout → return → search + overdue |
| **G2** | Circulation invariants hold under concurrency | Two simultaneous checkouts on same `holdingId` → exactly one succeeds (REQ-24, MVP.md §13.2) |
| **G3** | Idempotent checkout/return | Same `Idempotency-Key` replay → same outcome, no duplicate loan (MVP.md §13.3) |
| **G4** | RBAC enforced | Unauthorized roles rejected on write operations (REQ-21, MVP.md §13.4) |
| **G5** | SLO baselines met on seed data at §13.6 scale | p95 checkout/return ≤ 1200 ms; staff search ≤ 1500 ms (MVP.md §13.1) |
| **G6** | REQ-01 … REQ-25 mapped to shipped handlers/APIs | Traceability checklist §5 complete |

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

---

## 4. Implementation phases

Phases follow [MVP.md](MVP.md) §2 journey. Each phase ends with **verify** checks — do not start the next phase until they pass.

### Phase 0 — Foundation

**Goal:** Runnable skeleton with CI, DB migrations, module boundaries, auth stub.

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
| API shell: health, correlation id, error model | `X-Correlation-Id`, machine-readable errors | MVP.md §13.5, §10.5 |
| Auth middleware: role extraction | `ADMIN`, `LIBRARIAN`, `PATRON` on request context | REQ-21, ADR-010 |
| CI: unit + integration harness; migration on CI DB | Green pipeline on empty app | MVP.md §10.6 |
| Idempotency store | `idempotency_key`, actor, payload hash, response, `expires_at` | ADR-017, MVP.md §13.3 |

**Verify:** `GET /health` → 200; migration applies cleanly; CI green; module boundaries enforced.

---

### Phase 1 — Reference domain

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

**Verify:** Register student with `PatronType` + `ClassSection`; suspend/block rejected at domain layer; barcode lookup returns patron; audit fields populated (MVP.md §13.5).

---

### Phase 2 — Loan policy

**Goal:** Configurable limits before circulation (journey steps 2–3).

| Task | Handler / API | REQ |
|------|---------------|-----|
| Schema: `LoanRuleSet`, `Loan` (structure only) | `maxActiveLoans`, `loanPeriodDays` | REQ-12, REQ-23 |
| `ConfigureLoanRuleSet`, `UpdateLoanRuleSet` | Admin API | REQ-12 |
| `PolicyResolver`: `PatronType` → `LoanRuleSet`, compute `dueDate` | Fail closed if unmapped | REQ-16, ADR-005 |
| `MapPatronTypeToLoanRuleSet` | Via `UpdatePatronType` or dedicated command | MVP.md §2 step 2 |

**Verify:** Unmapped type → resolver error; mapped type → correct `dueDate` for given `loanPeriodDays`.

---

### Phase 3 — Catalog domain

**Goal:** Bibliographic records and lendable holdings (journey steps 4–5).

| Task | Handler / API | REQ |
|------|---------------|-----|
| Schema: `Catalog`, `Holding` | `DRAFT`/`PUBLISHED`/`SUPPRESSED`; `AVAILABLE`/`ON_LOAN`/`WITHDRAWN` | REQ-07–09, REQ-11 |
| `CreateCatalogDraft`, `UpdateCatalogMetadata` | title, language, optional ISBN, tags | REQ-07 |
| `PublishCatalog`, `SuppressCatalog` | Publish guards (CAT-*) | REQ-08 |
| `AddHoldingToCatalog`, `WithdrawHolding` | barcode + accession unique per tenant | REQ-09, REQ-11 |
| `HoldingLendabilityPort` adapter | Published catalog + `AVAILABLE` holding | REQ-17 |
| Indexes: barcode, accession, catalog status | Per MVP.md §10.4 | ADR-013 |

**Verify:** Unpublished catalog holding not lendable; withdrawn holding rejected; duplicate barcode fails.

---

### Phase 4 — Circulation kernel (critical path)

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

**Verify:**

- Happy path: checkout → holding `ON_LOAN`; return → `AVAILABLE`, `returnedAt` set.
- Reject: blocked patron, max loans exceeded, unpublished catalog, non-available holding.
- Concurrency: parallel checkout same holding → one winner.
- Idempotency: duplicate key → identical response, single loan.

---

### Phase 5 — Queries and staff operations

**Goal:** Discovery and operational visibility (journey step 8).

| Task | Handler / API | REQ |
|------|---------------|-----|
| `SearchCatalogStaff`, `ListHoldings` | Title/ISBN/barcode filters | REQ-10, REQ-25 |
| `ListOpenLoansByPatron` | Join labels from Reference/Catalog in read layer | REQ-15, REQ-19 |
| `ListOverdueLoans` | Open ∧ `today > dueDate` in library TZ (D6) | REQ-15, REQ-20 |
| RBAC on all endpoints | Per MVP.md §13.4 | REQ-21 |

**Verify:** Overdue list correct across timezone boundary; staff search p95 within MVP.md §13.1 on seed data at §13.6 scale.

---

### Phase 6 — Staff UI (optional thin slice)

**Goal:** Minimum desk-usable UI; API-first if UI slips.

| Screen | Actions |
|--------|---------|
| Patron lookup | Scan card / search by admission no. |
| Checkout / return | Scan patron + holding |
| Catalog search | Find title, list holdings |
| Overdue list | Operational report |
| Admin | Patron types, loan rules, class sections |

**Verify:** Librarian completes G1 journey without raw API calls.

---

### Phase 7 — Hardening and go-live

**Goal:** Production readiness per MVP.md §13 and §10.6.

| Task | Source |
|------|--------|
| Load test at §13.6 baselines | §13.6 |
| Lock-contention and idempotency regression suite | §13.2, §13.3 |
| Seed script: patron types, rules, sample catalog | §10.6 |
| Runbook: backup, migration rollback policy | §10.6 |
| Go-live checklist sign-off | §1.2 G1–G6 |

**Verify:** All G1–G6 criteria pass.

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

---

## 6. Testing strategy

| Layer | Focus |
|-------|--------|
| Unit | Aggregate invariants (REF-*, CAT-*, loan rules) |
| Integration | Handler + DB per module |
| Circulation | Orchestrator + ports + transaction + unique index |
| E2E | Full MVP.md §2 journey script |
| Performance | Checkout/return and search at MVP.md §13.6 scale |

**CI gate (MVP.md §10.6):** no deploy if migration or circulation tests fail.

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

---

## 8. Post-MVP (do not build now)

Bulk class issue, renewals, fines, guardian/notices, full OPAC, procurement — extend via new commands per [MVP.md](MVP.md) §9.3 without changing the orchestrator contract.

---

## 9. Related documents

| Document | Use in plan |
|----------|-------------|
| [MVP.md](MVP.md) | Scope, architecture, ADRs, guardrails, REQ traceability |
| [reference.md](reference.md) | Patron rules, entities |
| [catalog.md](catalog.md) | Catalog/holding rules |
| [loan.md](loan.md) | Loan rules, circulation |
| [research.md](research.md) | Deferred decisions (OQ-1 self-checkout) |
| [library_domain_model_final.md](library_domain_model_final.md) | Cross-domain overview |
