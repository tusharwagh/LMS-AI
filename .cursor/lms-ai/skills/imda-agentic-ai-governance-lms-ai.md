# LMS-AI — IMDA / Twelve-Factor conventions

Addendum to [imda-agentic-ai-governance/SKILL.md](../../../skills/imda-agentic-ai-governance/SKILL.md).

## LMS-AI conventions

| Concern | Where enforced |
|---------|----------------|
| Config in environment | `src/lms/config.py` — `agent_issue_enabled`, `agent_mock_llm`, `llm_provider(s)`, Langfuse keys |
| Backing services | `DATABASE_URL`, provider API keys, `LANGFUSE_*` — attach/detach per deploy |
| Build / release / run | `make ci-native` (build+test) → deploy script / `make deploy-native` (run only) |
| Stateless processes | Session + HITL state in DB via agent session layer, not worker RAM |
| Dev/prod parity | `make test-agent` with mock LLM; production requires real keys + `agent_issue_enabled` |
| Logs & traces | `src/lms/agent/tracing.py` — structlog audit + optional Langfuse spans |
| Admin one-offs | `make migrate`, `make seed`, `make validate-langfuse` — never invoked from graph nodes |

```python
# II. Config — feature flags and secrets from Settings, not code or prompts
from lms.config import get_settings

settings = get_settings()
if not settings.agent_issue_enabled:
    raise AgentDisabledError()
# AGENT_MOCK_LLM, LLM_PROVIDER, LANGFUSE_* all come from env / .env (not committed)

# VI. Processes — durable state in backing service, not process memory
# thread_id + checkpointer resume HITL; workers remain interchangeable

# XI. Logs — event stream to stdout; traces to Langfuse when configured
logger.info("agent_tool_invoked", tool=tool_name, thread_id=thread_id, args_redacted=True)
```

**Anti-patterns (12-factor):**

| Anti-pattern | Fix |
|--------------|-----|
| API keys in system prompt or graph state | Env vars via `Settings`; redact from checkpoints |
| Different graph topology in dev vs prod | Same code path; mock LLM / stub tools via config |
| Session stickiness required for HITL | Durable checkpointer + `thread_id`; any worker can resume |
| Writing logs to local files in containers | Stdout JSON; aggregate externally |
| Running migrations from agent tool nodes | Admin release step (`make migrate`) before run |
| Unpinned LLM library versions | Lock dependencies; tag releases with prompt/graph hash |

**Automated gate:** `make test-agent` with `AGENT_MOCK_LLM=true` — see [python-code-analysis-lms-ai.md](python-code-analysis-lms-ai.md).
