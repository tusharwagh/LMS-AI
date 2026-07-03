"""Idempotency store for circulation commands (ADR-017, MVP.md §13.3)."""

from sqlalchemy_idempotency import IDEMPOTENCY_TTL, IdempotencyResult, make_idempotency_model

from lms.shared.db.base import Base

IdempotencyRecord = make_idempotency_model(Base)

__all__ = ["IDEMPOTENCY_TTL", "IdempotencyRecord", "IdempotencyResult"]
