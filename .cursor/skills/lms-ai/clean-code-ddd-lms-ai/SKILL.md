---
name: clean-code-ddd-lms-ai
description: Addendum applying Clean Code, Kent Beck patterns, and Vaughn Vernon DDD to the LMS-AI K-12 library codebase — FastAPI, SQLAlchemy, LangGraph agent desk, workflows, import-linter boundaries, and Langfuse. Use when implementing or reviewing code in this repository, or alongside the clean-code-ddd-python skill for project-specific conventions.
---

# LMS-AI Stack Addendum

**Companion skill**: [clean-code-ddd-python](../../generic/clean-code-ddd-python/SKILL.md) (general principles).

This addendum maps those principles onto **this repository's** modules, ADRs, and enforced import contracts. Follow project rules in `.cursor/rules/` when they overlap — especially [sonarqube-quality.md](../../rules/generic/sonarqube-quality.md) and [sonarqube-quality-lms-ai.md](../../rules/lms-ai/sonarqube-quality-lms-ai.md).

**Verification:** [python-code-analysis](../../generic/python-code-analysis/SKILL.md) + [python-code-analysis-lms-ai.md](python-code-analysis-lms-ai.md) for Makefile targets, markers, and CI gates.

---

## Repository map

```
src/lms/
├── api/                 # HTTP shell: app, routers, workflows, agent router
├── agent/               # Desk agent: coordinator, tools, intent, messages, graph, masking
├── reference/           # Bounded context: patrons, patron types, class sections
├── catalog/             # Bounded context: catalog records, holdings
├── loan/                # Bounded context: loans, circulation, fulfillment
├── platform/            # LMS app platform: RBAC, API users, auth service, library calendar
├── shared/              # Reusable infra: db, http, auth/JWT, idempotency, logging, llm, observability, privacy
├── staff/               # Staff desk: React UI (`ui/`) + built static (`static/`) + router
└── config.py            # pydantic-settings (Settings)
```

**Python**: 3.12+, strict mypy, ruff (`E,F,I,UP,B`), line length 100.

---

## Bounded contexts and language

| Context | Core terms | Application entry points |
|---------|------------|--------------------------|
| `reference` | patron, patron type, class section, block | `ReferenceService` |
| `catalog` | catalog record, holding, lendability | `CatalogService` |
| `loan` | loan, circulation, fulfillment, loan rule set | `LoanService`, `CirculationOrchestrator`, `FulfillmentService` |

Use these terms in routes, schemas, agent prompts, and `ErrorCode` messages — not `user`, `item`, `record`.

---

## Layer conventions (per context)

```
{context}/
├── api/router.py, schemas.py    # FastAPI — auth via rbac types
├── application/
│   ├── service.py               # use cases
│   ├── commands/ queries/       # optional split
├── domain/
│   ├── enums.py, validation.py
│   └── ports.py                 # Protocol + frozen snapshots
└── infrastructure/
    ├── models/models.py         # SQLAlchemy ORM
    ├── adapters/                # anti-corruption to other contexts
    └── repositories/
```

### Where new code goes

| Task | Location |
|------|----------|
| HTTP endpoint | `{context}/api/router.py` + `schemas.py` |
| Business use case | `{context}/application/service.py` |
| Cross-context integration | Consumer `domain/ports.py` + provider `infrastructure/adapters/` |
| Staff multi-step flow | `lms/api/workflows/` (e.g. `SearchAndIssueWorkflow`) |
| Agent tool | `lms/agent/tools.py` → delegate to workflow/service |
| App wiring | `lms/api/composition.py` |
| Agent wiring | `lms/api/agent_composition.py` |
| Global API mount | `lms/api/domain_api.py`, `lms/api/app.py` |

---

## Import-linter contracts (enforced)

Violations fail CI. Do not "fix" by adding ignore without ADR.

| Contract | Rule |
|----------|------|
| Reference | Must not import `catalog.infrastructure` or `loan.infrastructure` |
| Catalog | Must not import `reference.infrastructure` or `loan.infrastructure` |
| Loan | Must not import `reference.infrastructure` or `catalog.infrastructure` |
| Agent | Must not import any domain `infrastructure` (explicit ignore list for composition/workflows only) |
| Shared | Must not import `platform` or any bounded context (`catalog`, `loan`, `reference`, `agent`) |
| Platform | Must not import bounded-context `infrastructure` or `agent` |

**DDD implication**: Cross-context data flows through **ports + adapters** or **workflow orchestration** in `api/workflows/`, not through ORM imports in the wrong context.

```python
# loan/domain/ports.py — port
class PatronEligibilityPort(Protocol):
    def check(self, patron_id: UUID) -> object: ...

# reference/infrastructure/adapters/patron_eligibility.py — adapter
class PatronEligibilityAdapter(PatronEligibilityPort): ...
```

---

## FastAPI patterns (this project)

### App assembly (`lms/api/app.py`)

- `create_app()` registers middleware from `shared/http/`: correlation ID, security headers, rate limit, plus CORS.
- Routers: health (`shared/http/health.py`), auth, `domain_api_router` (JWT required), agent, staff static.

### Authentication and RBAC (`lms/platform/auth/rbac.py`)

```python
StaffAuth = Annotated[AuthContext, Depends(require_roles(Role.ADMIN, Role.LIBRARIAN))]
AdminAuth = Annotated[AuthContext, Depends(require_roles(Role.ADMIN))]
```

Generic JWT deps live in `lms/shared/auth/deps.py`. Use `StaffAuth` for desk operations; `AdminAuth` for configuration. Do not duplicate role checks inside services.

### Errors (`lms/shared/http/errors.py`)

Always raise `AppError` with `ErrorCode` for domain and application failures:

```python
raise AppError(
    ErrorCode.DOMAIN_RULE_VIOLATION,
    "Patron is blocked from borrowing",
    status_code=422,
    details={"patron_id": str(patron_id)},
)
```

Handlers produce: `{ "code", "message", "retriable", "details" }`. Do not introduce alternate error shapes.

### Composition root

Build orchestrators in `composition.py`; build agent desk in `agent_composition.py` — routes call those factories instead of assembling adapters inline.

### Workflows

`SearchAndIssueWorkflow`, `ReturnBookWorkflow` are **application-level process managers** for staff UI and agent tools. They:

- Coordinate `ReferenceService`, `CatalogService`, `CirculationOrchestrator`, validators
- Return frozen result dataclasses (`IssueStartResult`, `IssueCommitResult`)
- Support idempotency via `lms/shared/idempotency/`

Keep workflow steps explicit (`start`, `validate`, `commit`, `cancel`) — Composed Method pattern.

### API design alignment

Follow [api-and-interface-design.md](../../rules/generic/api-and-interface-design.md) and [api-and-interface-design-lms-ai.md](../../rules/lms-ai/api-and-interface-design-lms-ai.md): validate at route boundary with Pydantic; consistent errors; additive schema changes; `Idempotency-Key` on mutating staff endpoints.

---

## Domain patterns (loan example)

### CirculationOrchestrator

Coordinates checkout/return through ports — the tactical DDD **application service** for circulation invariants. Inject:

- `PatronEligibilityPort`
- `HoldingCirculationPort`
- `PolicyResolverPort`

### ValidationReport

Domain validation returns structured reports, not booleans alone:

```python
report = validator.validate(...)
if not report.is_valid:
    raise AppError(ErrorCode.DOMAIN_RULE_VIOLATION, report.summary(), details=...)
```

### Frozen value types

Prefer `@dataclass(frozen=True, slots=True)` for results and port snapshots (`ResolvedPolicy`, `HoldingSnapshot`, `ToolResult`, `AgentTurnResult`).

---

## Agent desk (`lms/agent/`)

Architecture (ADR-021, ADR-025):

| Module | Role |
|--------|------|
| `coordinator.py` | `IssueAgentCoordinator` — session, intent, approval, turn lifecycle |
| `tools.py` | `IssueTools` — allowlisted delegation to workflows/services |
| `intent_parser.py` | `LLMIntentParser` → `ParsedIntent` / `IntentAction` (defined in `schemas.py`) |
| `session.py` | `AgentIssueSession`, `PendingApproval`, in-memory `SessionStore` |
| `masking.py` | Desk pseudonyms (`PseudonymMap`) + HITL `sanitize_approval_details` |
| `constants.py` | `AGENT_ID` (tracing) and `AGENT_CHARTER_NAME` (IMDA charter) |
| `llm_intent_prompt.py` | `LLM_INTENT_SYSTEM` — all workflows; governance + session_context |
| `messages.py` | Staff-facing desk copy — single source for `assistant_message` and approval summaries |
| `schemas.py` | `IntentAction`, `ParsedIntent`, agent API Pydantic models |
| `tracing.py` | Re-export facade → `shared.observability.tracing.LangfuseTracing` (SDK v4; `_langfuse_observation` propagates body exceptions) |
| `graph.py` | Minimal LangGraph SOP (structural; business logic stays in coordinator) |

### Tool design rules

```python
READ_TOOL_NAMES   # search, validate, status
WRITE_TOOL_NAMES  # commit, transition, cancel — require human approval path
RESTRICTED_TOOL_NAMES  # never bound: direct_db, admin_api, remote_mcp, ...
```

- Tools return `ToolResult(ok, message, data)` — consistent agent-consumable shape.
- Use pseudonyms in tool output; map back to real IDs only inside coordinator on approved writes.
- **Multi-match disambiguation:** return candidate lists with business keys (**PATRON_N**, **COPY_N**, **LOAN_N**, CARD-*, ADM-*); never fail hard on ambiguity — staff select via `select_*` intents.
- Patron resolution delegates to `ReferenceService` / `parse_patron_query()` — same as WF-01/WF-02 `patron_query`.
- `IssueTools` receives `SearchAndIssueWorkflow` and `FulfillmentService` — not raw ORM queries.
- **Slot guards (Composed Method):** one prerequisite per private helper; compose for multi-slot tools.
  - `_patron_id(slots, action)` / `_holding_id(slots, action)` — each returns `UUID | ToolResult` with an intent-specific message from `messages.py` (`missing_patron_for`, `missing_copy_for`).
  - **Response builders** in `messages.py` echo the staff query and parsed intent (`patron_search_results`, `catalog_search_results`, `issue_ready`, `help_for_unknown_intent`) — plain desk language, not API jargon.
  - `_patron_and_holding(slots, action)` — calls both guards in order; first missing slot wins with its action-specific message.
  - Callers unwrap with `isinstance(..., ToolResult)` before proceeding.
  - `IssueSlots.has_patron_and_holding` — boolean predicate for coordinator approval paths (different user-facing message).

### Coordinator rules

- `handle_message` → parse intent → `_apply_intent` → persist session.
- `resume(approved=...)` executes pending write after human approval.
- Check `agent_issue_enabled` and operator session ownership before any action.
- Enforce `agent_max_tool_calls_per_turn`.

### LangGraph (`graph.py`)

Fixed edges: `enter → parse → govern → END`. The graph documents SOP structure (IMDA control); **do not** move loan rules into graph nodes.

### Settings (`lms/config.py`)

Agent/LLM/Langfuse config via `Settings`: `groq_api_key`, `llm_model`, `agent_mock_llm`, `langfuse_*`. Feature flag: `agent_issue_enabled`.

### Governance overlap

For agent guardrails, human accountability, tool allowlists, and Twelve-Factor deployment (config in `Settings`, stateless workers, stdout logs), also apply [imda-agentic-ai-governance](../imda-agentic-ai-governance/SKILL.md).

### Agent desk copy (`messages.py`)

All librarian-visible strings live in `messages.py`. Coordinator and tools import `from lms.agent import messages as desk` — never inline user-facing prose in `coordinator.py` or `tools.py`.

| Guideline | Pattern |
|-----------|---------|
| Plain language | Patron names, titles, barcodes — no UUIDs, pseudonyms, tool names, "slots", "HITL", `holding_id` |
| Intent-specific | Helpers take `IntentAction` — `missing_patron_for(action)`, `missing_copy_for(action)` |
| Query echo | Include the librarian’s typed query in search/success/not-found — `patron_search_results(query, ...)`, `no_patron_found(query)` |
| Issue + next action | Every helper states what is wrong/missing **and** what to do next |
| CHAT routing | `intent_parser.py` → `IntentAction.CHAT` + `greeting_reply()` / `help_reply()` for greetings and how-to; must not misroute to patron search |
| Approvals | `commit_approval_prompt`, `cancel_approval_prompt`, `fulfillment_transition_prompt` — plain summary + approve/deny consequence |

Coordinator passes `intent.action` into tool guards and uses desk helpers for turn responses. Staff UI (`src/lms/staff/ui/`) uses **MVC**: `models/` (API), `controllers/` (hooks), `views/*View.tsx` (presentation), `config/navigation.ts` (CRM-style grouped nav). Renders `assistant_message`, `pending_approval.summary`, and `agent_disclosure` verbatim — backend is the single source of truth. Build with `make staff-ui-build`.

**Verify copy changes:** `make test-agent` and `pytest tests/agent/test_intent_and_masking.py`.

---

## Observability

- **structlog** via `lms/shared/logging.py` — structured fields, correlation ID from middleware.
- **Langfuse**: SDK **4.x** (`langfuse>=4.0,<5`); agent spans via `LangfuseTracing` in `shared/observability/tracing.py`; LiteLLM `"langfuse"` callback skipped when SDK lacks `langfuse.version`.
- Never log raw patron names/barcodes in production traces; use `redact_for_audit`.

---

## Database and sessions

- SQLAlchemy 2.x style: `session.scalar(select(...))`, `session.add`, `session.commit`.
- Request-scoped session via `lms/shared/db/deps.py` (`DbSession`).
- ORM models live only in `{context}/infrastructure/models/` — not in API or agent layers.

---

## Testing markers (`pyproject.toml`)

| Marker | Use |
|--------|-----|
| `unit` | Pure logic, no DB |
| `integration` | DB + services |
| `e2e` | API journeys (`tests/e2e/`) |
| `hardening` | Concurrency, idempotency |
| `agent` | Agent desk, intent, tools |

Agent tests: mock LLM (`agent_mock_llm`); assert intent routing and tool delegation, not model prose.

**Full analysis guide:** [python-code-analysis/SKILL.md](../python-code-analysis/SKILL.md) and [lms-ai.md](../python-code-analysis/lms-ai.md).

### Pre-PR static (required)

```bash
make lint
PYTHONPATH=src .venv/bin/mypy
```

### Pre-PR dynamic (by change scope)

| Scope | Command |
|-------|---------|
| Default | `make test-unit` + tests for touched module |
| DB / services | `make test-integration` |
| API / workflows | `make test-e2e` |
| Writes / circulation | `make test-hardening` |
| Agent desk | `make test-agent` |
| Full gate | `make ci-native` |

Run: `pytest`, `ruff check`, `mypy`, `lint-imports` (import-linter).

---

## Implementation checklist (LMS-AI PR)

- [ ] Code in correct bounded context and layer
- [ ] No forbidden cross-context infrastructure imports
- [ ] `AppError` + `ErrorCode` for failures; no ad-hoc HTTP errors in domain
- [ ] Pydantic schemas at API edge; frozen dataclasses inside application
- [ ] New cross-context need → port + adapter, not shared ORM
- [ ] Staff flows in `api/workflows/`; agent tools delegate there
- [ ] Write tools behind approval path in coordinator
- [ ] Staff-facing agent copy in `messages.py` only; intent-aware + query echo
- [ ] RBAC on routes (`StaffAuth` / `AdminAuth`)
- [ ] Idempotency for mutating workflow commits where applicable
- [ ] Tests with appropriate marker; static analysis clean (ruff, mypy, import-linter)
- [ ] Dynamic tests pass for change scope (see python-code-analysis/lms-ai.md)
- [ ] PII masked in agent audit paths

---

## Quick references

| Topic | Path |
|-------|------|
| Circulation orchestration | `lms/loan/application/circulation_orchestrator.py` |
| Issue workflow | `lms/api/workflows/search_and_issue.py` |
| Agent coordinator | `lms/agent/coordinator.py` |
| Tool allowlist | `lms/agent/tools.py` |
| Import contracts | `pyproject.toml` `[tool.importlinter]` |
| Static & dynamic analysis | `.cursor/skills/generic/python-code-analysis/` + `.cursor/skills/lms-ai/python-code-analysis-lms-ai.md` |
| Security hardening | `.cursor/rules/generic/security-and-hardening.md` + `.cursor/rules/lms-ai/security-and-hardening-lms-ai.md` |
| Code simplification | `.cursor/rules/generic/code-simplification.md` |
| SonarQube quality gates | `.cursor/rules/generic/sonarqube-quality.md` + `.cursor/rules/lms-ai/sonarqube-quality-lms-ai.md` |
