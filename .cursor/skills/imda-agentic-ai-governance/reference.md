# IMDA MGF Reference — Agentic AI

Supplement to [SKILL.md](SKILL.md). Read when doing formal risk assessment or architecture review.

## Framework source

- **Document:** Model AI Governance Framework for Agentic AI, Version 1.5 (Updated 5 June 2026)
- **Publisher:** IMDA Singapore
- **Nature:** Voluntary guidance; living document

## Four dimensions (summary)

1. **Assess and bound risks upfront** — risk assessment, agent limits, identity/permissions
2. **Make humans meaningfully accountable** — value-chain responsibility, effective oversight
3. **Implement technical controls and processes** — dev controls, pre-deploy testing, monitoring, change management
4. **Enable end-user responsibility** — transparency, training, tradecraft preservation

## Risk types (§1.2.2)

| Risk | Example |
|------|---------|
| Erroneous actions | Wrong date, flawed code with security holes |
| Unauthorised actions | Action outside scope or without required approval |
| Biased or unfair actions | Skewed hiring, procurement, grant decisions |
| Data breaches | Leak or wrongful modification of PII/confidential data |
| Disruption to connected systems | Delete production data, API flooding |

## Multi-agent systemic risks (§1.2.3)

- **Speed and volume** — harm before oversight reacts; alert fatigue
- **Cascading effects** — early error amplifies downstream
- **Agent sprawl** — uncontrolled proliferation, provenance gaps
- **Miscoordination** — agents pursue conflicting interpretations
- **Conflict** — agents optimise opposing goals (refunds vs revenue protection)
- **Collusion** — emergent coordinated behaviour without explicit instruction
- **Unpredictability** — exponential outcome space; cross-boundary interactions hard to test

**LangGraph mitigations:** explicit supervisor routing, typed state schemas, bounded handoffs, central graph registry, integration tests on composed graphs.

## Risk assessment factors

### Impact (severity if risk manifests)

| Factor | Question |
|--------|----------|
| Domain / use case | What is error tolerance? How critical are supported processes? |
| Sensitive data access | PII, confidential data, persistent memory across sessions? |
| External systems | Third-party APIs, web, untrusted data sources? |
| Scope of actions | Read-only vs write? Few tools vs computer-use breadth? |
| Reversibility | Can mistakes be undone? Contractual obligations triggered? |

### Likelihood (probability risk manifests)

| Factor | Question |
|--------|----------|
| Autonomy | SOP-bound vs free planning? |
| Task complexity | Steps, analysis depth, policy nuance? |
| External exposure | Internal KB only vs open web? |
| Third-party solutions | Visibility and control over vendor agents? |
| System complexity | Single sequential graph vs many interacting agents? |

## Action-space vs autonomy (§1.1.3)

**Action-space:** what the agent *can* do (tools, permissions, read/write).

**Autonomy:** how much the agent *decides* how to act (instructions, human involvement).

| Human involvement model | Description |
|-------------------------|-------------|
| Agent proposes, human operates | Approve every action |
| Agent and human collaborate | Approval at significant steps; human can intervene anytime |
| Agent operates, human approves | Approval only at critical steps / failures |
| Agent operates, human observes | Post-hoc audit only |

Map tiers to LangGraph: higher autonomy → more `interrupt` nodes, governance checkpoints, and monitoring.

## Agent identity best practices (§2.1.2)

**Identification:** unique agent identity; tied to supervisor/human/dept; capacity recorded; centrally catalogued.

**Authorisation:** scoped, least-privilege, time/session-bound, non-transferable; agent permissions ≤ delegating human; delegations logged.

## Human oversight checkpoints (§2.2.2)

Require approval before:

- High-stakes decisions (sensitive edits, legal/healthcare finals, liability-triggering actions)
- Irreversible actions (delete, send comms, payment)
- Outlier behaviour (out-of-scope access, anomalous routes)
- User-defined boundaries (personal spend limits)

**Approval UX:** contextual, digestible, risk-visible; support approve / reject / edit-plan.

**Oversight effectiveness metrics:**

- Human override rate (too low → rubber stamping)
- Approval response time (too fast → automation bias)
- Outlier human reviewers

## Control types (§2.3.1)

| Type | Reliability | Use when |
|------|-------------|----------|
| Structural | Highest | Tool allowlists, workflow edges, environment separation |
| Rule-based | High | Policy nodes, rate limits, schema validation |
| Model / prompt | Variable | Harmful content detection, nuanced policy |

**Runtime controls:** intervene during execution (rate limits, validation, block before act).

## Pre-deployment test dimensions (§2.3.2)

- Overall task execution
- Policy / SOP compliance
- Tool calling (correct tool, args, order, permissions)
- Robustness (errors, edge cases, injection)
- Full workflow (not final output only)
- Individual and multi-agent system level
- Realistic environment (calibrated to risk)
- Repeated runs across varied datasets

## Related frameworks (Annex A)

- CSA Singapore — Draft Addendum on Securing Agentic AI
- GovTech Singapore — Agentic Risk & Capability Framework
- OWASP — Agentic AI Threats and Mitigations
- AI Verify / previous IMDA MGF (2020), MGF for GenAI (2024)

## Tiering example (Dayos case study)

| Tier | Profile | Autonomy |
|------|---------|----------|
| Tier 1 | Low severity, reversible | Full automation + periodic audit |
| Tier 2 | Moderate, partial reversibility | Diagnose auto; execute with human sign-off |
| Tier 3 | High severity, limited reversibility | No autonomous execution |

Apply similar tiering to LangGraph graphs: different compiled graphs or conditional routing per tier.

## OpenClaw case study lessons (IMDA)

- Avoid mission-critical deployment without hardening
- Avoid single all-powerful agent
- Prefer system-level approval over prompt guardrails
- Log all actions; test disallowed actions pre-deploy
- Train personnel on misuse risks

## Langfuse observability mapping

| Enterprise charter requirement | Langfuse surface |
|-------------------------------|------------------|
| Tool invocation logging | Trace spans via `CallbackHandler` or `@observe` |
| Correlation IDs | `trace_id`, `session_id`, custom `metadata` (`agent_id`, `thread_id`) |
| Execution time | Span latency (ms) per tool/model call |
| Tool success/failure rate | Scores and dashboard filters on span status |
| Human overrides | Custom events or scores on HITL approve/deny |
| Audit review | Langfuse UI + export; align retention with data classification |
| Eval regression | Datasets, prompt versions, run scores |

Environment: `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` (self-hosted or cloud).
