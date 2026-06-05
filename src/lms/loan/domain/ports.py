"""Integration ports consumed by CirculationOrchestrator (ADR-004)."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol
from uuid import UUID


@dataclass(frozen=True, slots=True)
class ResolvedPolicy:
    loan_rule_set_id: UUID
    max_active_loans: int
    loan_period_days: int
    due_date: date


class PatronEligibilityPort(Protocol):
    def check(self, patron_id: UUID) -> object: ...


class HoldingLendabilityPort(Protocol):
    def check(self, holding_id: UUID) -> object: ...


class PolicyResolverPort(Protocol):
    def resolve(self, patron_type_id: UUID) -> ResolvedPolicy: ...
