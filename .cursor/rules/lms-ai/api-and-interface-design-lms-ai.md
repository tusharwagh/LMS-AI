---
name: api-and-interface-design-lms-ai
description: LMS-AI agent API contract addendum for /api/v1/agent/issue/*. Use with generic api-and-interface-design rule.
---

# LMS-AI agent API (`/api/v1/agent/issue/*`)

Staff chat consumes typed responses from `lms/agent/schemas.py`:

| Field | Role |
|-------|------|
| `assistant_message` | Primary librarian-visible reply — built in `messages.py`; plain language; issue + next action |
| `pending_approval.summary` | HITL card text — approval prompts from `messages.py` |
| `pending_approval.details` | Structured data for UI (not primary copy) |
| `agent_disclosure` | Fixed transparency string on every response |
| `session_summary` | Slot state for UI/debug — not end-user prose |

**Contract rules:**

- Do not embed tool names, UUIDs, or internal field names in `assistant_message`
- Additive optional fields only on response models
- Changing message wording is observable (Hyrum's Law) — update `tests/agent/test_intent_and_masking.py` when copy changes

**See also:** [api-and-interface-design.md](../generic/api-and-interface-design.md) (generic API design rule).
