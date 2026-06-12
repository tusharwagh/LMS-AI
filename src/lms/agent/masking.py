"""PII pseudonymization and audit redaction (ADR-026)."""

from __future__ import annotations

import re
from uuid import UUID

_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN_REDACTED]"),
    (re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"), "[CARD_REDACTED]"),
]


def redact_for_audit(text: str) -> str:
    for pattern, replacement in _PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class PseudonymMap:
    """Maps real UUIDs to stable pseudonyms within one agent session."""

    def __init__(self) -> None:
        self._patron: dict[UUID, str] = {}
        self._holding: dict[UUID, str] = {}
        self._loan: dict[UUID, str] = {}
        self._fulfillment: dict[UUID, str] = {}

    def patron(self, patron_id: UUID, display_name: str) -> str:
        if patron_id not in self._patron:
            self._patron[patron_id] = f"PATRON_{len(self._patron) + 1}"
        return self._patron[patron_id]

    def holding(self, holding_id: UUID, barcode: str) -> str:
        if holding_id not in self._holding:
            self._holding[holding_id] = f"COPY_{len(self._holding) + 1}"
        return self._holding[holding_id]

    def loan(self, loan_id: UUID) -> str:
        if loan_id not in self._loan:
            self._loan[loan_id] = f"LOAN_{len(self._loan) + 1}"
        return self._loan[loan_id]

    def fulfillment(self, fulfillment_id: UUID) -> str:
        if fulfillment_id not in self._fulfillment:
            self._fulfillment[fulfillment_id] = f"FULF_{len(self._fulfillment) + 1}"
        return self._fulfillment[fulfillment_id]

    def resolve_patron(self, pseudonym: str) -> UUID | None:
        for uid, label in self._patron.items():
            if label == pseudonym:
                return uid
        return None

    def resolve_holding(self, pseudonym: str) -> UUID | None:
        for uid, label in self._holding.items():
            if label == pseudonym:
                return uid
        return None
