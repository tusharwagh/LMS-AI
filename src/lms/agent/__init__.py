"""Agent desk edge module (MVP Phase 8, ADR-025).

LMS-specific: coordinator, tools, session, messages, masking (pseudonyms).
Shared infra: LLM (`shared.llm`), tracing (`shared.observability`),
PII redaction (`shared.privacy`).
Writes delegate to `api/workflows/` — never domain infrastructure directly.
"""

from lms.agent.constants import AGENT_CHARTER_NAME, AGENT_ID

__all__ = ["AGENT_CHARTER_NAME", "AGENT_ID"]
