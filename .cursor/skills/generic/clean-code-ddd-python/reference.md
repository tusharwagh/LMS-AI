# DDD Reference — Python / FastAPI / LangGraph

Supplement to [SKILL.md](SKILL.md). Read when designing new bounded contexts or cross-context integration.

## Context map

See your project overlay under `.cursor/skills/<project>/` for the bounded-context map when present.

## Entity vs value object (Python)

| Kind | Traits | Python shape |
|------|--------|--------------|
| Entity | Identity matters; mutable lifecycle | ORM model or class with `id: UUID` |
| Value object | Defined by attributes; immutable | `dataclass(frozen=True, slots=True)` |
| Snapshot | Read-only view from another context | Frozen dataclass in `domain/ports.py` |

## Application command template

```python
class SomeApplicationService:
    def __init__(self, session: Session, port: SomePort) -> None:
        self._session = session
        self._port = port

    def execute(self, cmd: SomeCommand) -> SomeResult:
        entity = self._load(cmd.id)
        self._domain_rule(entity, cmd)
        self._session.commit()
        return SomeResult.from_entity(entity)
```

Commands are explicit dataclasses or typed parameters — not loose dicts.

## When to add a new module

| Signal | Action |
|--------|--------|
| New REST resource in existing context | Add to `{context}/api/router.py` + schemas |
| New use case in existing context | Add to `{context}/application/service.py` or `commands/` |
| New cross-context rule | Port in consumer `domain/ports.py`, adapter in provider `infrastructure/adapters/` |
| Multi-step staff journey | New workflow module under `api/workflows/` |
| Agent capability | Add tool delegating to workflow/service |

## LangGraph placement rule

If a node contains `if patron_blocked` or SQL, it is in the wrong place. Graph nodes should only route state; coordinators and application services own decisions.

## Verification

Before merge: [python-code-analysis/SKILL.md](../python-code-analysis/SKILL.md) — static (ruff, mypy, import-linter) + dynamic pytest by marker. Sonar gates: [sonarqube-quality.md](../../rules/generic/sonarqube-quality.md).

Ports return snapshots (`PatronEligibilitySnapshot`, `HoldingSnapshot`) — LSP/DIP; never leak foreign ORM into orchestrators.
