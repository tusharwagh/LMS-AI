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


@dataclass(frozen=True, slots=True)
class HoldingSnapshot:
    holding_id: UUID
    catalog_id: UUID
    is_published: bool
    holding_status: str
    circulating: bool
    is_lendable: bool


class PatronEligibilityPort(Protocol):
    def check(self, patron_id: UUID) -> object: ...


class HoldingCirculationPort(Protocol):
    def lock_for_checkout(self, holding_id: UUID) -> HoldingSnapshot: ...

    def mark_on_loan(self, holding_id: UUID) -> None: ...

    def lock_for_return(self, holding_id: UUID) -> None: ...

    def mark_available(self, holding_id: UUID) -> None: ...


class PolicyResolverPort(Protocol):
    def resolve(self, patron_type_id: UUID) -> ResolvedPolicy: ...
