---
name: sonarqube-quality-lms-ai
description: LMS-AI SonarQube addendum — AppError patterns, agent desk smells, Makefile/CI gates. Use with generic sonarqube-quality rule.
---

# LMS-AI SonarQube addendum

Adjust thresholds in Sonar project settings; the generic rule is the baseline — this file is the **LMS-AI engineering default**.

## Domain error pattern

Domain failures → `AppError`; never mix ad-hoc HTTP shapes.

## Testing (Sonar coverage alignment)

| Requirement | LMS-AI practice |
|-------------|-----------------|
| New behavior has tests | unit → integration → e2e by scope |
| Name tests as specs | `test_issue_rejected_when_patron_blocked` |
| No assertion on privates | Assert HTTP envelope, state, side effects |
| Agent tests mock LLM | `AGENT_MOCK_LLM=true`; assert routing |
| Security regressions | `tests/hardening/` |

## FastAPI / API smells (LMS-AI)

| Smell | Fix |
|-------|-----|
| Missing auth on route | `StaffAuth` / router-level `Depends` |
| Inconsistent response shape | Single `{code, message, retriable, details}` via `AppError` |

## Agent / LangGraph smells

| Smell | Fix |
|-------|-----|
| Business rules in graph nodes | Coordinator + application services |
| Business rules in prompts only | Structural allowlist + HITL |
| Unbounded tool loop | `agent_max_tool_calls_per_turn` |
| PII in traces | `redact_for_audit`, pseudonyms |
| Unrestricted tools | `RESTRICTED_TOOL_NAMES` deny-by-default |
| Multi-slot guard in one helper | Split `_patron_id` / `_holding_id`; compose in `_patron_and_holding` |
| Scattered staff-facing strings | Centralize in `lms/agent/messages.py`; intent + query-echo builders |
| Technical jargon in desk copy | No UUIDs, pseudonyms, tool names, "slots", "HITL" in `assistant_message` |
| Secrets or flags in prompts/graph state | Env via `Settings`; validate at startup |
| Dev-only graph fork | Same graph; `AGENT_MOCK_LLM` / stub tools in config |
| Log files inside containers | Structured stdout + Langfuse spans (redacted) |

Cross-reference: [imda-agentic-ai-governance](../../../skills/imda-agentic-ai-governance/SKILL.md) (IMDA + Twelve-Factor).

**See also:** [sonarqube-quality.md](../../generic/rules/sonarqube-quality.md) (generic SonarQube rule).
