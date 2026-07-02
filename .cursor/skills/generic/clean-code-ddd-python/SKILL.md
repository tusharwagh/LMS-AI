---
name: clean-code-ddd-python
description: Applies Clean Code (Uncle Bob), SOLID, Implementation Patterns (Kent Beck), and Implementing DDD (Vaughn Vernon) when writing or reviewing Python code with FastAPI, LangChain, LangGraph, and Langfuse. Use when implementing features, refactoring, designing modules, agent tools, API endpoints, domain logic, or when the user mentions clean code, SOLID, DDD, bounded contexts, ports and adapters, or tactical patterns.
---

# Clean Code, SOLID, Implementation Patterns, and DDD (Python / FastAPI / LangGraph)

Synthesize Clean Code, **SOLID**, Kent Beck patterns, and Vaughn Vernon DDD into one workflow for this stack. Prefer **surgical changes** that match existing project conventions; do not impose patterns the codebase does not use.

For repo-specific layout, import rules, and module map, read your project overlay under `.cursor/skills/<project>/` when present.

**Verification:** run static and dynamic analysis per [python-code-analysis](../python-code-analysis/SKILL.md). SonarQube-aligned quality gates: [sonarqube-quality.md](../../rules/generic/sonarqube-quality.md).

## When to use

- Designing or reviewing FastAPI routes, Pydantic schemas, dependencies
- Adding application services, domain rules, or infrastructure adapters
- Building LangGraph nodes, agent coordinators, or `@tool` wrappers
- Refactoring for clarity without behavior change
- Splitting modules or defining bounded-context boundaries

## Decision workflow

```
1. Name the concept in ubiquitous language (DDD)
2. Place it in the correct layer and bounded context (DDD)
3. Apply SOLID at module and class boundaries
4. Keep functions/methods one level of abstraction (Clean Code + Beck)
5. Validate at system boundaries only (Clean Code + FastAPI)
6. Wire dependencies explicitly; no hidden globals (Beck + DDD + DIP)
7. Trace agent/tool calls at the boundary (Langfuse)
```

---

## Clean Code (Robert C. Martin) — Python adaptations

### Names and functions

- **Reveal intent**: `resolve_patron_by_card` not `get_data`; `CirculationOrchestrator` not `LoanManager`.
- **One thing**: If you need "and" to describe a function, split it.
- **Small**: Target &lt;20 lines per function; extract when nesting exceeds two levels.
- **One level of abstraction**: High-level orchestration calls named steps; do not mix SQL, HTTP, and business rules in one block.

```python
# Good: orchestration reads as a procedure
def start_issue(self, patron_id: UUID) -> IssueStartResult:
    patron = self._require_patron(patron_id)
    validation = self._validator.validate_patron(patron.id)
    results = self._catalog.search_lendable(...)
    return IssueStartResult(...)
```

### Comments and formatting

- Comments explain **why** (policy, ADR, regulatory constraint), not **what**.
- Match project `ruff` settings (line length, import order). Formatting is not optional.

### Error handling

- **Do not** return error codes from deep domain logic; raise domain-typed exceptions (`AppError`, `ValidationReport`).
- **Do** translate to HTTP at the API boundary via exception handlers.
- **Do not** swallow exceptions; log with context at the boundary, then fail clearly.

### Classes

- Small, cohesive classes; prefer `dataclass(frozen=True, slots=True)` for value-like bundles.
- Avoid god objects; split read vs write responsibilities when lifecycles differ (Beck + Vernon).

### Tests

- One concept per test; name tests as specifications: `test_issue_rejected_when_patron_blocked`.
- Test behavior, not implementation details (no asserting private method calls).

---

## SOLID principles — Python / FastAPI adaptations

SOLID complements Clean Code and DDD: it governs **how modules collaborate** without rigidity or leakage.

### Single Responsibility (SRP)

A class or module should have **one reason to change** — one actor or concern.

| Good (example) | Violation |
|---------------|-----------|
| `CirculationOrchestrator` — checkout/return only | Router that validates JWT, runs SQL, and formats JSON |
| `IssueEligibilityValidator` — issue rule checks | `IssueTools` embedding loan policy instead of delegating |
| `FulfillmentService` — fulfillment lifecycle | Agent graph node with SQL |

**Rule:** If a change to auth, HTTP, or UI forces edits in domain code, SRP is broken.

### Open/Closed (OCP)

Open for extension, closed for modification — add behavior via **new types**, not editing stable cores.

```python
# Extend via new port adapter — do not edit CirculationOrchestrator for each patron source
class PatronEligibilityAdapter(PatronEligibilityPort):
    def check(self, patron_id: UUID) -> PatronEligibilitySnapshot: ...
```

- New fulfillment mode → extend enum + service branch or strategy, not rewrite workflow from scratch.
- New staff journey → new workflow class in `api/workflows/`, not `if workflow == ...` in router.

Prefer **data** (`LoanRuleSet`) and **ports** over growing `if/elif` chains in orchestrators.

### Liskov Substitution (LSP)

Subtypes must honor the **contract** of the abstraction — no surprising exceptions or weaker guarantees.

- Any `PatronEligibilityPort` implementation must return a complete `PatronEligibilitySnapshot` or raise consistently (not `None` silently).
- Test stubs used in integration tests must behave like production adapters for the exercised paths.
- Pydantic response models: subclasses or variants must not drop required fields callers rely on.

**Red flag:** `Protocol` implementer that returns ORM models when the consumer expects snapshots.

### Interface Segregation (ISP)

Clients should not depend on methods they do not use. Prefer **small ports** over fat interfaces.

```python
# Good: focused ports (loan/domain/ports.py)
class HoldingCirculationPort(Protocol):
    def lock_for_checkout(self, holding_id: UUID) -> HoldingSnapshot: ...
    def mark_on_loan(self, holding_id: UUID) -> None: ...
```

- Split read vs write tool sets for agents (`READ_TOOL_NAMES` / `WRITE_TOOL_NAMES`) — ISP for LLM tool binding.
- Do not pass full `Session` into domain logic when only a port is needed.

### Dependency Inversion (DIP)

High-level policy depends on **abstractions**; low-level details depend on those abstractions too.

```python
# High-level: CirculationOrchestrator
# Abstractions: PatronEligibilityPort, HoldingCirculationPort, PolicyResolverPort
# Low-level: adapters in */infrastructure/adapters/
```

- Wire in `composition.py` / FastAPI `Depends` — not `from lms.catalog.infrastructure.models import ...` in orchestrators.
- Agent tools depend on `SearchAndIssueWorkflow`, not raw SQLAlchemy queries.

### SOLID quick checklist

- [ ] Each class/module: one clear responsibility
- [ ] New behavior added via port, workflow, or data — not central `if` sprawl
- [ ] Port implementations substitutable in tests
- [ ] Ports and tool sets are minimal for the consumer
- [ ] Domain/application code depends on abstractions; infrastructure injected

---

## Implementation Patterns (Kent Beck) — Python adaptations

### Simple design (Beck's four rules)

1. Passes all tests
2. Reveals intention (names, small methods)
3. No duplication
4. Minimize elements (fewest classes/functions that still read clearly)

### Composed Method

Break algorithms into small private methods invoked in sequence. Each private method does one step at a single abstraction level.

### Guard Clause

Replace nested `if` trees with early returns / raises:

```python
def process(data: PatronModel | None) -> Result:
    if data is None:
        raise AppError(ErrorCode.NOT_FOUND, "Patron not found", status_code=404)
    if not data.is_active:
        raise AppError(ErrorCode.DOMAIN_RULE_VIOLATION, "Patron blocked")
    return self._do_work(data)
```

For agent tools that must return `ToolResult` instead of raising, use **one guard per prerequisite** and compose (Composed Method):

```python
def _patron_id(self, slots: IssueSlots, action: IntentAction) -> UUID | ToolResult:
    if slots.patron_id is None:
        return ToolResult(False, desk.missing_patron_for(action), {})
    return slots.patron_id

def _patron_and_holding(
    self, slots: IssueSlots, action: IntentAction,
) -> tuple[UUID, UUID] | ToolResult:
    patron_id = self._patron_id(slots, action)
    if isinstance(patron_id, ToolResult):
        return patron_id
    holding_id = self._holding_id(slots, action)
    if isinstance(holding_id, ToolResult):
        return holding_id
    return patron_id, holding_id
```

Do not combine unrelated prerequisite checks in one function when callers need distinct messages or reuse single-slot guards.

### Message builder pattern (staff-facing copy)

When guards or coordinators need user-visible text, extract **named message builders** (not inline strings):

- One module per UX surface — e.g. `app/agent/messages.py` for staff-facing copy
- Builders take **intent context** (`IntentAction`) and **query echo** (what the user typed)
- Each builder returns a complete sentence: **issue statement + next action**
- Callers stay thin: `return ToolResult(False, desk.missing_patron_for(action), {})`

Avoid scattering desk copy across tools/coordinator — duplication drifts and breaks intent-specific wording.

### Explaining Variable

When an expression is dense, assign to a well-named local:

```python
policy = self._policy_resolver.resolve(patron.patron_type_id)
due_date = self._library_today + timedelta(days=policy.loan_period_days)
```

### Strategy via Protocol (not inheritance hierarchy)

```python
class PolicyResolverPort(Protocol):
    def resolve(self, patron_type_id: UUID) -> ResolvedPolicy: ...
```

Inject the strategy; tests use a stub implementation (Self Shunt).

### Factory Method

Use when construction is non-trivial or context-dependent:

```python
def get_circulation_orchestrator(session: Session) -> CirculationOrchestrator:
    return CirculationOrchestrator(
        session=session,
        patron_eligibility=PatronEligibilityAdapter(session),
        ...
    )
```

### Test-Driven Development (when adding behavior)

1. Write a failing test for the next behavior slice
2. Minimal code to pass
3. Refactor with tests green
4. Repeat

For bug fixes: reproduce with a test first, then fix.

---

## Implementing DDD (Vaughn Vernon) — tactical patterns

### Ubiquitous language

Use domain terms consistently across code, APIs, agent prompts, and docs: **patron**, **holding**, **circulation**, **fulfillment**, **loan rule set** — not generic CRUD names.

### Bounded contexts

Each context owns its model and language. Cross-context integration uses **ports**, **adapters**, or **application workflows** — not direct infrastructure imports across contexts.

Typical layers per context:

| Layer | Responsibility | Depends on |
|-------|----------------|------------|
| `api` | HTTP schemas, routers | `application`, Pydantic |
| `application` | Use cases, orchestration, workflows | `domain`, ports |
| `domain` | Rules, enums, ports (`Protocol`), value types | nothing inward |
| `infrastructure` | SQLAlchemy models, adapters, repos | `domain` |

### Aggregates and consistency

- Identify aggregate roots (e.g. `Loan`, `Patron` in their contexts).
- Enforce invariants inside the aggregate or a domain service; commit at aggregate boundary.
- Prefer **one transaction per application command**; orchestrators coordinate multiple aggregates via ports.

### Application services vs domain services

- **Application service**: coordinates use case, loads data, calls domain, persists, publishes side effects.
- **Domain service**: pure rule spanning multiple entities when it does not belong on one entity.

### Repositories and ports

- **Repository** (infrastructure): persistence for one aggregate type.
- **Port** (`Protocol` in `domain/ports.py`): integration need another context fulfills via adapter.

```python
# Port in loan/domain — adapter in reference/infrastructure
class PatronEligibilityPort(Protocol):
    def check(self, patron_id: UUID) -> PatronEligibilitySnapshot: ...
```

### Anti-corruption layer

Adapters translate foreign models into snapshots/value objects your context understands (`HoldingSnapshot`, `ResolvedPolicy`). Never leak ORM models across context boundaries in orchestrators.

### Workflows (Saga / process manager)

Multi-step staff processes (search → validate → commit) belong in `application` or `api/workflows` as explicit classes with named steps — not scattered across routers.

### Anti-patterns to avoid

| Anti-pattern | Fix |
|--------------|-----|
| Anemic domain (all logic in routers) | Move rules to domain/application |
| Leaky repository (returns ORM everywhere) | Return domain types or DTOs at application edge |
| Shared database model across contexts | Adapter + snapshot at boundary |
| Smart UI / smart agent doing domain work | Agent calls application services via tools |

---

## FastAPI boundary patterns

### Contract first

Define Pydantic request/response schemas before route bodies. Response shapes are part of the contract (Hyrum's Law).

### Validate at the edge

```python
@router.post("/issues", response_model=IssueResponse)
def start_issue(body: IssueStartRequest, auth: StaffAuth, db: DbSession) -> IssueResponse:
    result = workflow.start(patron_id=body.patron_id, ...)
    return IssueResponse.from_result(result)
```

Internal services trust typed inputs; they do not re-validate HTTP-level concerns.

### Dependencies

- `Depends(require_auth)`, `require_roles` for authorization at router or route level.
- Session via `DbSession`; construct orchestrators in `composition.py`, not in every route.

### Errors

Single error envelope everywhere (`code`, `message`, `retriable`, `details`). Raise `AppError`; never mix raw `HTTPException` shapes for domain failures.

### Idempotency

Mutating endpoints that staff retry accept `Idempotency-Key`; cache responses at the application/workflow layer.

---

## LangChain / LangGraph / Langfuse patterns

### Agent architecture

| Piece | Responsibility |
|-------|----------------|
| **Coordinator** | Session, intent, approval gates, turn lifecycle |
| **Tools** | Thin, allowlisted wrappers over application/workflows |
| **Graph** | Structural control (fixed edges, interrupts) — not business rules |
| **Intent parser** | NL → typed `ParsedIntent` (bounded vocabulary) |

**Rule**: Business rules live in domain/application layers. Tools **delegate**; they do not embed loan policy.

### Tools

```python
@dataclass(frozen=True, slots=True)
class ToolResult:
    ok: bool
    message: str
    data: dict[str, object]

def validate_issue(self, slots: IssueSlots) -> ToolResult:
    report = self._workflow.validate(slots)
    return ToolResult(report.is_valid, report.summary(), {"report": report.to_dict()})
```

- Separate **read** vs **write** tool sets; bind only authorized tools.
- Use `RESTRICTED_TOOL_NAMES` deny-by-default for prohibited capabilities.
- Return compact DTOs; redact PII for audit (`redact_for_audit`).

### LangGraph

- State: `TypedDict` with explicit fields; avoid untyped `dict` soup.
- Nodes: one transition per node; conditional edges for governance/approval.
- Use `interrupt` / resume for human-in-the-loop — not prompt-only "please confirm".
- Checkpointer for thread state when persistence is required.

### Langfuse

- Trace at coordinator/tool boundaries: `trace`, `span`, `generation` for LLM calls.
- Propagate `session_id`, `operator_id`, `agent_id` as metadata.
- Never log secrets or raw PII in traces; align with masking utilities.

### LLM calls

- Prefer structured output / intent enums over free-form parsing when safety matters.
- Cap tool calls per turn (`agent_max_tool_calls_per_turn`).
- Mock LLM in tests (`agent_mock_llm`); integration tests assert tool routing, not model creativity.

---

## Refactoring checklist

Before merging:

- [ ] Ubiquitous language used in names and API fields
- [ ] Code sits in correct layer and bounded context
- [ ] No cross-context infrastructure imports (run `import-linter`)
- [ ] Functions are small, one abstraction level, guard clauses where needed
- [ ] Validation only at HTTP/agent input boundaries
- [ ] Domain rules not duplicated in routers, tools, or prompts
- [ ] Errors use `AppError` / `ErrorCode` consistently
- [ ] Agent tools delegate to workflows/services
- [ ] SOLID: SRP layers, DIP via ports/composition, ISP-sized ports and tool sets
- [ ] Static analysis: ruff, mypy, import-linter (see [python-code-analysis](../python-code-analysis/SKILL.md))
- [ ] Dynamic analysis: pytest at appropriate markers; behavior specs green
- [ ] Langfuse/masking applied at observability boundaries

## Additional resources

- DDD layering and context map detail: [reference.md](reference.md)
- Static & dynamic analysis workflow: [python-code-analysis/SKILL.md](../python-code-analysis/SKILL.md)
- SonarQube-aligned rules: [sonarqube-quality.md](../../rules/generic/sonarqube-quality.md)
