"""Backward-compatible facade — implementation lives in lms.shared.observability."""

from lms.shared.observability.tracing import AgentTracing, LangfuseTracing

__all__ = ["AgentTracing", "LangfuseTracing"]
