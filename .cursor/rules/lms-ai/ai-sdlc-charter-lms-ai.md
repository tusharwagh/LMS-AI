---
name: ai-sdlc-charter-lms-ai
description: LMS-AI AI SDLC charter addendum — charter path, bounded contexts, and project-specific gates. Use with generic ai-sdlc-charter rule.
---

# LMS-AI — AI SDLC charter addendum

Extends [ai-sdlc-charter.md](../generic/ai-sdlc-charter.md).

## Charter

| Item | Path |
|------|------|
| **Charter** | `docs/ai-sdlc/CHARTER.md` |
| **Index** | `docs/ai-sdlc/README.md` |

## Project-specific gates

| Area | Rule |
|------|------|
| Bounded contexts | import-linter contracts — no cross-context imports |
| Agent desk | `make test-agent`; HITL on writes; [IMDA skill](../../skills/generic/imda-agentic-ai-governance/SKILL.md) |
| Security | [security-and-hardening-lms-ai.md](security-and-hardening-lms-ai.md) |
| Non-trivial decisions | [doubt-driven-development.md](../generic/doubt-driven-development.md) |

## Traceability

Link to `REQ-XX` ([plan-mvp.md](../../docs/plan-mvp.md)) and `#NNN` issues when applicable.

**See also:** [ai-sdlc-charter.md](../generic/ai-sdlc-charter.md), [CHARTER.md](../../docs/ai-sdlc/CHARTER.md).
