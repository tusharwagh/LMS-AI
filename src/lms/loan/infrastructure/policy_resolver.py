"""Resolves PatronType -> LoanRuleSet and due date (ADR-005)."""

from uuid import UUID

from lms.loan.domain.ports import ResolvedPolicy


class PolicyResolver:
    def resolve(self, patron_type_id: UUID) -> ResolvedPolicy:
        raise NotImplementedError("Phase 2 — Loan policy")
