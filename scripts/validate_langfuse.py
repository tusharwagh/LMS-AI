#!/usr/bin/env python3
"""Validate Langfuse credentials and emit a test agent/tool span (G13 ops check)."""

from __future__ import annotations

import sys

from lms.agent.tracing import AgentTracing
from lms.config import get_settings

AGENT_ID = "LMS Desk Issue & Fulfillment Agent"


def main() -> int:
    get_settings.cache_clear()
    settings = get_settings()

    if not settings.langfuse_public_key or not settings.langfuse_secret_key:
        print("SKIP: Langfuse keys not set — validation skipped (set LANGFUSE_* in .env to enable)")
        return 0

    print(f"host: {settings.langfuse_host}")
    tracing = AgentTracing(settings)

    if tracing._client is None:
        print("FAIL: Langfuse client did not initialize (check logs for langfuse_client_init_failed)")
        return 1

    if not tracing.auth_ok():
        print(
            "FAIL: Langfuse auth_check failed — verify keys and LANGFUSE_HOST / LANGFUSE_BASE_URL "
            "(US cloud: https://us.cloud.langfuse.com)"
        )
        return 1

    print("auth_ok: True")
    with tracing.turn_span(
        session_id="langfuse-validation",
        operator_id="ops",
        agent_id=AGENT_ID,
        action="validate",
    ):
        with tracing.tool_span(
            tool_name="search_patrons",
            session_id="langfuse-validation",
            operator_id="ops",
            agent_id=AGENT_ID,
        ):
            pass

    tracing.flush()
    print("OK: test spans flushed — check Langfuse for turn:validate and tool:search_patrons")
    return 0


if __name__ == "__main__":
    sys.exit(main())
