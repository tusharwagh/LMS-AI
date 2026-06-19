"""Postgres spend logging via LiteLLM CustomLogger."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from litellm.integrations.custom_logger import CustomLogger
from sqlalchemy import Boolean, DateTime, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, Session, mapped_column

from lms.shared.db.base import Base
from lms.shared.db.session import SessionLocal
from lms.shared.llm.cost import extract_cost_usd, extract_usage

logger = structlog.get_logger(__name__)


class LlmSpendLog(Base):
    """Persisted LLM completion spend (LiteLLM gateway callback)."""

    __tablename__ = "llm_spend_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, default="completion")
    model: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(String(64), nullable=False, default="unknown")
    prompt_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(nullable=False, default=0)
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 8), nullable=True)
    cached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    session_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    operator_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )


class LlmSpendLogger(CustomLogger):
    """Write LiteLLM success/failure events to Postgres."""

    def log_success_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        self._persist(kwargs, response_obj, success=True)

    def log_failure_event(
        self,
        kwargs: dict[str, Any],
        response_obj: Any,
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        self._persist(kwargs, response_obj, success=False)

    def _persist(self, kwargs: dict[str, Any], response_obj: Any, *, success: bool) -> None:
        litellm_params = kwargs.get("litellm_params") or {}
        metadata = litellm_params.get("metadata") or kwargs.get("metadata") or {}
        if not isinstance(metadata, dict):
            metadata = {}

        usage = extract_usage(response_obj) if success else None
        cost_usd = kwargs.get("response_cost")
        if cost_usd is None and success:
            cost_usd = extract_cost_usd(response_obj)

        model = str(kwargs.get("model") or litellm_params.get("model") or "unknown")
        provider = str(
            litellm_params.get("custom_llm_provider")
            or kwargs.get("custom_llm_provider")
            or model.split("/", 1)[0]
        )
        purpose = str(metadata.get("purpose") or "completion")
        session_id = metadata.get("session_id")
        operator_id = metadata.get("operator_id")
        cached = bool(metadata.get("cached") or kwargs.get("cache_hit"))

        skip_keys = {"purpose", "session_id", "operator_id", "cached"}
        extra = {k: v for k, v in metadata.items() if k not in skip_keys}
        if not success:
            extra["success"] = False

        session: Session = SessionLocal()
        try:
            session.add(
                LlmSpendLog(
                    purpose=purpose,
                    model=model,
                    provider=provider,
                    prompt_tokens=usage.prompt_tokens if usage else 0,
                    completion_tokens=usage.completion_tokens if usage else 0,
                    total_tokens=usage.total_tokens if usage else 0,
                    cost_usd=float(cost_usd) if cost_usd is not None else None,
                    cached=cached,
                    session_id=str(session_id) if session_id else None,
                    operator_id=str(operator_id) if operator_id else None,
                    metadata_json=json.dumps(extra, ensure_ascii=True) if extra else None,
                )
            )
            session.commit()
        except Exception as exc:
            session.rollback()
            logger.warning("llm_spend_log_failed", error=str(exc))
        finally:
            session.close()
