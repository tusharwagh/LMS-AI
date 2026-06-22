---
name: imda-agentic-ai-governance
description: Applies Singapore IMDA Model AI Governance Framework for Agentic AI (MGF v1.5) and the Twelve-Factor App methodology when designing, building, reviewing, or deploying LangChain/LangGraph agents. Use when implementing agentic AI, human-in-the-loop workflows, tool access controls, multi-agent systems, MCP integrations, agent guardrails, Langfuse observability, data/app security guardrails, cloud-native deployment, environment configuration, or when the user mentions IMDA, MGF, 12-factor, twelve-factor, agent governance, or responsible agent deployment.
---

# IMDA Agentic AI Governance (LangChain / LangGraph)

Apply the [IMDA Model AI Governance Framework for Agentic AI](https://www.imda.gov.sg/-/media/imda/files/about/emerging-tech-and-research/artificial-intelligence/mgf-for-agentic-ai.pdf) (MGF v1.5, May 2026) when building or reviewing LangChain/LangGraph agents. The framework is voluntary; treat it as a structured checklist, not legal advice.

## When to use

- Designing a new agent or multi-agent graph
- Adding tools, MCP servers, or external API access
- Implementing human approval, guardrails, or rollout controls
- Pre-deployment testing or production monitoring for agents
- Code review of agentic features

## Agent component map (IMDA → LangGraph)

| IMDA component | LangChain / LangGraph surface |
|----------------|------------------------------|
| Model | `ChatModel`, `init_chat_model` |
| Instructions | System prompt, `create_react_agent` prompt |
| Memory | `checkpointer`, `store`, thread state |
| Planning & reasoning | Graph nodes, ReAct loop, planner node |
| Tools | `@tool`, `ToolNode`, `bind_tools` |
| Protocols | MCP adapters, A2A, custom tool schemas |
| Controls | Graph topology, conditional edges, `interrupt`, middleware |
| Logging & monitoring | Langfuse traces, structured logs, audit tables |

## Workflow

Copy and track:

```
Governance progress:
- [ ] 1. Assess and bound risks upfront
- [ ] 2. Make humans meaningfully accountable
- [ ] 3. Implement technical controls and processes
- [ ] 4. Enable end-user responsibility
- [ ] Residual risk accepted and documented
```

Treat the four dimensions as **iterative**. If monitoring surfaces anomalies, revisit earlier dimensions.

---

## 12-Factor agent deployment

Apply [Twelve-Factor App](https://12factor.net/) discipline alongside IMDA §3 (technical controls and lifecycle). Governance controls must survive production operations — config drift, sticky sessions, and non-reproducible releases undermine structural guardrails.

```
12-Factor progress (agent deploy):
- [ ] I. Codebase — one repo; graph/prompt/tools versioned together
- [ ] II. Config — secrets and toggles in environment only
- [ ] III. Dependencies — explicit, lockfile-pinned manifests
- [ ] IV. Backing services — DB, LLM, Langfuse as attached resources
- [ ] V. Build, release, run — immutable releases; no runtime compiles
- [ ] VI. Processes — stateless workers; durable state in backing services
- [ ] VII. Port binding — self-contained HTTP/gRPC export
- [ ] VIII. Concurrency — scale processes; bound in-process tool loops
- [ ] IX. Disposability — fast startup, graceful shutdown, bounded retries
- [ ] X. Dev/prod parity — same graph code; mock LLM only in test config
- [ ] XI. Logs — stdout event streams + Langfuse traces (redacted)
- [ ] XII. Admin — migrations, seeds, evals as one-off release tasks
```

### Factor map (IMDA ↔ 12-factor)

| Factor | Agent / LangGraph requirement | IMDA alignment |
|--------|------------------------------|----------------|
| **I. Codebase** | One deployable per agent product; graph, prompts, tool schemas in git | Change management; audit trail for graph versions |
| **II. Config** | `Settings` / env vars for keys, feature flags, model IDs — never in prompts or checkpoints | Secrets excluded from state; tier toggles without redeploying logic |
| **III. Dependencies** | `pyproject.toml` + lockfile; pin LangChain/LangGraph/LiteLLM versions | Supply-chain hygiene; reproducible eval runs |
| **IV. Backing services** | Postgres checkpointer, Langfuse, LLM APIs via URLs/keys — swappable without code change | Sandbox vs prod credentials; least-privilege per environment |
| **V. Build, release, run** | CI builds artifact → tagged release → `run` starts processes only | Pre-deploy tests on immutable artifact; phased rollout |
| **VI. Processes** | API workers hold no in-memory session authority; thread state in DB checkpointer | Checkpoint security; tenant isolation |
| **VII. Port binding** | Uvicorn/FastAPI (or gRPC) binds port; no external web-server coupling | Agent exposed as attachable service behind auth |
| **VIII. Concurrency** | Scale web workers horizontally; cap `agent_max_tool_calls_per_turn` per request | Rate limits; circuit breakers on tool path |
| **IX. Disposability** | SIGTERM drains in-flight turns; SOP halt-and-notify instead of infinite retry | Bounded autonomy; no zombie agent loops |
| **X. Dev/prod parity** | Same compiled graph in all envs; `AGENT_MOCK_LLM=true` only in CI/dev config | Realistic pre-deploy tests without prod keys in dev |
| **XI. Logs** | `structlog` → stdout; Langfuse for tool/model spans with redacted args | Audit cadence; no PII in log files |
| **XII. Admin** | `make migrate`, `make seed`, eval datasets — not mixed into request path | Admin tasks audited separately from agent traces |

**Project-specific conventions:** see [imda-agentic-ai-governance-lms-ai.md](../../lms-ai/imda-agentic-ai-governance-lms-ai.md) when deploying LMS-AI.

For factor-by-factor review notes, see [reference.md](reference.md#twelve-factor-app-agentic-ai).

---

## Enterprise agent charter (required before production)

Document and enforce this charter for every deployed agent. Fill placeholders per use case; enforce structurally in graph code, not prompt-only.

### 1. Scope and authorization

| Field | Document | Enforce in LangGraph |
|-------|----------|----------------------|
| Agent identity | Name, role, owning team | `configurable["agent_id"]`; distinct service account / API key |
| System authority level | Read-only, or read/write with approval limits | Tool binding; separate read vs write `ToolNode` |
| Authorized actions | Allowlisted tools and APIs | Per-agent `tools=` list; MCP server whitelist |
| Restricted actions | Prohibited operations (deletes, prod DB writes, mass messaging) | Omit tools; governance node blocks; deny-by-default |

**Template — fill per agent:**

```
Agent Identity: [Agent Name / Role]
System Authority Level: [e.g., Read-only, or Read/Write with approval limits]
Authorized Actions:
  - [Tool/API 1, e.g., CRM Read API]
  - [Tool/API 2, e.g., Email Sending (requires human review)]
Restricted Actions (strictly prohibited):
  - [e.g., Deleting records, Modifying production database, Mass messaging without opt-in]
```

```python
# Structural enforcement — restricted tools never bound
AUTHORIZED_TOOLS = [crm_read, kb_search]
RESTRICTED_TOOL_NAMES = {"delete_record", "prod_db_write", "mass_email"}

def governance_checkpoint(state) -> Command:
    call = state["pending_tool_call"]
    if call["name"] in RESTRICTED_TOOL_NAMES:
        return Command(goto="human_review")
    return Command(goto="tools")
```

### 2. Operational workflows and SOPs

Agents executing multi-step processes must follow defined SOPs sequentially — no ad-hoc replanning around required steps.

**Template:**

```
Trigger/Input: [Event or prompt that starts the workflow]
Execution Steps:
  1. [Step 1]
  2. [Step 2]
  3. [Step 3]
Error Handling: Halt execution and notify [User/Department] on tool failure — no recursive self-troubleshooting.
```

**LangGraph patterns:**

- **SOP-bound:** fixed `StateGraph` edges (linear or DAG), not open-ended ReAct for regulated flows
- **Error handling:** route failures to `interrupt()` or terminal error node; never auto-retry unbounded loops
- **Notification:** emit structured event to approval channel (Slack, email, dashboard) with `thread_id` and Langfuse `trace_id`

```python
def sop_step(state):
    try:
        result = execute_step(state)
        return {"step_result": result, "current_step": state["current_step"] + 1}
    except ToolError as e:
        return Command(goto="halt_and_notify", update={"error": str(e), "halt_reason": "tool_failure"})

def halt_and_notify(state):
    interrupt({
        "type": "sop_failure",
        "step": state["current_step"],
        "error": state["error"],
        "notify": "[User/Department]",
    })
    return Command(goto="end")
```

### 3. Human-in-the-loop (HITL) handoffs

Human intervention is mandatory for high-risk actions. Automation bias is a governance failure.

**Approval thresholds — human review required when:**

- Financial transactions exceed $[X]
- External, unverified emails or messages are generated
- PII is accessed or shared outside approved scope
- Action matches restricted-action list or governance policy violation

**Approval protocol:**

1. Agent pauses via `interrupt()` before irreversible execution
2. Logs intended output to [Approval Dashboard / Slack / Email] with digestible summary
3. Waits for [Admin / Team Lead] confirmation via `Command(resume=...)`
4. Deny-by-default if approval infrastructure is unavailable

```python
def hitl_gate(state):
    if requires_human_approval(state):
        decision = interrupt({
            "action": state["pending_action"],
            "pii_involved": state.get("pii_accessed", False),
            "financial_amount": state.get("amount"),
            "approval_channel": "[Approval Dashboard / Slack / Email]",
            "summary": state["human_summary"],
        })
        if not decision.get("approved"):
            return Command(goto="revise_plan")
    return Command(goto="execute")
```

### 4. Guardrails and constraints (data and app security)

Built-in limitations to prevent unintended or malicious behaviour. Prefer structural controls over prompt-only rules.

#### Data privacy

- Mask or redact sensitive data in logs, traces, and approval payloads (SSNs, credit cards, full account numbers)
- Never store secrets, tokens, or raw PII in graph checkpoints unless encrypted and retention-bound
- Apply field-level redaction before Langfuse export and before human approval UIs

```python
import re

PII_PATTERNS = [
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN_REDACTED]"),
    (re.compile(r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b"), "[CARD_REDACTED]"),
]

def redact_for_audit(text: str) -> str:
    for pattern, replacement in PII_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
```

#### App security

Align with application security boundaries (see [security-and-hardening.md](../../rules/generic/security-and-hardening.md)):

| Threat | Agent-specific control |
|--------|------------------------|
| Injection (prompt, tool args) | Validate tool inputs with strict schemas; never pass raw LLM output to SQL/shell |
| Privilege escalation | Least-privilege tool binding; agent identity ≠ human admin credentials |
| Information disclosure | Redact PII in traces; generic errors to end users; no secrets in state |
| Unauthorized actions | Governance node + HITL before write/external comms |
| Supply chain (MCP, third-party tools) | Server whitelist; sandbox execution; scoped OAuth tokens |

#### Safety boundaries

- Refuse queries or tasks that violate [Company Ethics Policy / Acceptable Use Policy]
- Implement as governance node (deterministic deny rules) + optional LLM judge for edge cases
- Log refused requests with reason code (no sensitive user content in logs)

#### Safe output

- Generated content or code must land in a restricted directory (`/output` or equivalent sandbox) before publish or deploy
- No direct write to production paths, public buckets, or live APIs without HITL
- Version and audit all artifacts before release

```python
SAFE_OUTPUT_DIR = "/output"  # restricted, non-production

def write_agent_artifact(filename: str, content: str) -> str:
    path = os.path.join(SAFE_OUTPUT_DIR, filename)
    # HITL or governance gate required before promote_to_production(path)
    with open(path, "w") as f:
        f.write(content)
    return path
```

### 5. Observability and auditing (Langfuse)

Every tool invocation, data access, and model decision must be traceable.

**Langfuse setup (LangChain / LangGraph):**

```python
from langfuse import Langfuse
from langfuse.langchain import CallbackHandler

langfuse = Langfuse()  # LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
handler = CallbackHandler()

config = {
    "callbacks": [handler],
    "metadata": {
        "agent_id": "[Agent Name / Role]",
        "thread_id": thread_id,
        "risk_tier": "medium",
    },
}
graph.invoke(input_state, config=config)
```

**What to log (per trace span):**

- Timestamp, `agent_id`, `thread_id`, `trace_id`
- Tool name, args (redacted), success/failure, latency (ms)
- Model decision summary (not full chain-of-thought)
- HITL events: approval requested, approved/denied, approver role
- PII access flags and redaction applied

**Metrics tracked:**

| Metric | Purpose |
|--------|---------|
| Execution time (ms) | Latency SLOs, anomaly detection |
| Tool success/failure rate | Reliability, misconfiguration alerts |
| Human overrides required | Automation bias signal; policy tuning |
| Policy blocks / refusals | Safety boundary effectiveness |
| PII access count | Data governance compliance |

**Audit cadence:**

- Logs reviewed [Weekly / Monthly] by compliance team
- Langfuse dashboards for override rate, failure spikes, new tool usage
- Correlate `trace_id` with application audit tables for end-to-end accountability
- Retention policy aligned with data classification (PII traces may need shorter TTL)

```python
from langfuse import observe

@observe(name="tool_invocation")
def audited_tool_call(tool_name: str, args: dict):
  # Langfuse records span; args should be redacted before observe
  return execute_tool(tool_name, args)
```

---

## 1. Assess and bound risks upfront

### Risk assessment (before coding)

Score the use case on IMDA factors. Document tier (low / medium / high) and residual risk acceptance.

**Impact factors:** domain error tolerance, sensitive data access, external system access, read vs write scope, action reversibility.

**Likelihood factors:** autonomy level, task complexity, exposure to untrusted inputs, third-party opacity, multi-agent complexity.

If risk is high and the task is deterministic, prefer a **workflow graph** over open-ended ReAct.

### Bound by design (prefer structural over prompt-only)

IMDA: enforce limits at system level; prompt-layer guardrails can be bypassed or "forgotten."

| Control | LangGraph pattern |
|---------|-------------------|
| Least-privilege tools | Per-agent `tools=` list; separate graphs per function (IT vs HR) |
| Read-only tools | Separate read/write tools; omit write tools from `ToolNode` |
| SOP-bound workflow | Fixed `StateGraph` edges instead of free planning |
| Sandboxed execution | Isolated tool backends; no production credentials in dev graphs |
| Multi-agent scope | Supervisor with specialist subgraphs; avoid one super-agent |
| Agent identity | Per-agent service account, API key, or token in `configurable` |

```python
# Tiered tool binding — tools are structural limits, not prompts
low_risk_tools = [search_kb, get_status]
high_risk_tools = []  # never bound; human-only path

graph = create_react_agent(model, tools=low_risk_tools, checkpointer=checkpointer)
```

### Multi-agent patterns (IMDA §1.1.2)

- **Sequential:** `StateGraph` with linear or DAG edges — predictable, auditable
- **Supervisor:** parent node routes to specialist subgraphs as tools
- **Swarm / handoff:** `Command(goto=...)` with explicit handoff rules

Avoid unbounded agent sprawl: central catalog of deployed graphs, versions, and permissions.

For full risk-factor tables and threat-modelling notes, see [reference.md](reference.md).

---

## 2. Make humans meaningfully accountable

### Responsibility allocation

Document owners across the agent lifecycle:

| Role | Owns |
|------|------|
| Use case owner | Suitability, oversight model, residual risk sign-off |
| Engineering | Graph design, tools, testing, change management |
| Security | Threat model, access controls, incident response |
| End users | Review outputs, report issues, retain domain skills |

For third-party models/tools/MCP hosts: contract obligations, observability, and fallback when opacity is too high.

### Meaningful human oversight (not rubber-stamping)

See **Enterprise agent charter §3** for approval thresholds and protocol. IMDA checkpoints requiring human approval:

- High-stakes or irreversible actions (payments, deletes, external comms)
- PII access or sharing outside approved scope
- Outlier behaviour (unexpected tool, scope violation)
- User-defined thresholds (e.g. purchase limit exceeding $X)

**LangGraph implementation:**

```python
from langgraph.types import interrupt, Command

def approval_gate(state):
  decision = interrupt({
    "action": state["pending_action"],
    "risk": state["risk_tier"],
    "summary": state["human_summary"],  # digestible, not raw logs
  })
  if decision["approved"]:
    return Command(goto="execute")
  return Command(goto="revise_plan")

# Compile with durable checkpointer + thread_id for resume
graph = builder.compile(checkpointer=postgres_checkpointer)
# Resume: graph.invoke(Command(resume={"approved": True}), config)
```

Practices:

- Place `interrupt()` **before** irreversible tool calls, not after
- Support edit-then-approve (human modifies plan in checkpoint) for complex steps
- **Deny by default** if approval infrastructure is unavailable
- Audit: track override rate and approval latency; low override / fast approval may indicate automation bias

### Automation bias mitigations

- Contextual approval payloads (plain-language explanation + confidence, not chain-of-thought dumps)
- **LMS-AI desk copy:** `pending_approval.summary` and `assistant_message` from `messages.py` — patron names, titles, barcodes; no UUIDs, tool names, or internal jargon (meaningful oversight for librarians)
- Periodic human review samples of auto-approved actions
- Training on agent failure modes (hallucinated tools, stale policy, injection)

---

## 3. Implement technical controls and processes

### Control hierarchy (IMDA §2.3.1)

Prefer in order:

1. **Structural** — graph topology, tool allowlists, separate environments
2. **Rule-based** — deterministic policy nodes, input validation, rate limits
3. **Model / prompt-layer** — output filters, LLM judges (higher latency, less reliable)

Insert a **governance node** between decide and act:

```python
def governance_checkpoint(state) -> Command:
  action = state["pending_tool_call"]
  if violates_policy(action):
    return Command(goto="human_review")  # or interrupt()
  if exceeds_budget(state):
    return Command(goto="end")
  return Command(goto="tools")

builder.add_edge("agent", "governance")
builder.add_conditional_edges("governance", route_on_decision)
```

### Controls by component

| Component | Controls |
|-----------|----------|
| Planning | Plan logging; clarification `interrupt` before execution; reflection node |
| Tools | Strict schemas; least privilege; no write to sensitive DBs unless required |
| MCP | Server whitelist; sandbox code execution; OAuth/scoped tokens |
| Multi-agent | Typed handoff schemas; limit shared memory; contain third-party agents in ecosystem |
| Runtime | Rate limits, circuit breakers, anomaly alerts on tool calls |

### Lifecycle

**Development:** secure defaults; no permissive tool config in production graphs.

**Pre-deployment testing** (adapt for agents):

- Task execution accuracy end-to-end
- Policy / SOP adherence (approval gates fire when required)
- Tool selection, args, order, permissions
- Robustness to edge cases and injection
- Multi-agent emergent behaviour (test together, not only per agent)
- Repeated runs on varied datasets (stochastic stability)

Use Langfuse scores/datasets for evals, `langgraph dev` test threads, and deterministic assertions on tool calls where possible. Correlate eval runs with production traces via shared `agent_id` and prompt version tags.

**LMS-AI automated gate:** `make test-agent` with `AGENT_MOCK_LLM=true` — see [python-code-analysis-lms-ai.md](../../lms-ai/python-code-analysis-lms-ai.md). Static: ruff + import-linter on `lms/agent/` (no infrastructure imports).

**Deployment:** phased rollout (user cohort / feature flag), continuous monitoring, versioned graph definitions. Follow **12-Factor V** — build and test in CI (`make ci-native`), promote immutable artifact, run processes separately; no hot-editing graph code in production.

**Change management:** treat graph, tool, and prompt changes as releases; assess cascade impact in multi-agent systems. Tag releases with graph/prompt version in Langfuse metadata for trace correlation.

### Checkpoint security

LangGraph checkpointers store full state and conversation history. Apply production DB controls: encryption, least-privilege access, tenant isolation, retention policy. Treat checkpoint stores as sensitive as primary app data.

---

## 4. Enable end-user responsibility

### Transparency

Disclose to users:

- When an agent is acting vs a human
- What tools/systems the agent can access
- What actions require their approval
- Limitations and that outputs may be wrong

Surface in UI: agent status, pending approvals from `interrupt` payloads, audit links.

### User education

- Training for oversight duties and failure modes
- Preserve foundational tradecraft (agent augments, does not replace professional judgment)
- Differentiate internal integrators vs external-facing users (stricter guardrails externally)

---

## Implementation checklist (LangGraph)

### Enterprise charter
- [ ] Agent identity, authority level, authorized/restricted actions documented
- [ ] SOPs defined with explicit error-handling (halt + notify, no unbounded retry)
- [ ] HITL thresholds set (financial, PII, external comms)
- [ ] Approval protocol wired (`interrupt` → channel → `resume`)
- [ ] Safe output directory enforced; no direct prod writes

### Graph design
- [ ] Risk tier documented; tools match tier (least privilege)
- [ ] No single all-powerful agent with unrestricted tools
- [ ] High-risk actions route through `interrupt` or governance node
- [ ] Multi-agent boundaries explicit; shared state minimized
- [ ] Agent/service identity distinct from human users

### Controls & security
- [ ] Structural limits enforced (tool binding, graph edges), not prompt-only
- [ ] MCP servers whitelisted; untrusted servers sandboxed
- [ ] Runtime policy node or middleware on tool path
- [ ] Deny-by-default when approval path fails
- [ ] PII redaction in logs, traces, and approval payloads
- [ ] Tool input validation; no raw LLM output to SQL/shell
- [ ] Secrets excluded from graph state and checkpoints
- [ ] Checkpoint store secured and retention defined

### Accountability & observability
- [ ] Owners named (use case, engineering, security)
- [ ] Langfuse traces with `agent_id`, `thread_id`, redacted tool args
- [ ] Metrics: latency, tool success rate, override rate, policy blocks
- [ ] Audit cadence defined (weekly/monthly compliance review)
- [ ] Third-party components documented with residual risk

### 12-Factor deployment
- [ ] Config (keys, flags, model IDs) in environment — not prompts, code constants, or graph state
- [ ] Same graph/prompt code in dev, CI, and prod; mocks only via config (`AGENT_MOCK_LLM`)
- [ ] Backing services (DB, LLM, Langfuse) attached via URLs/keys; swappable per environment
- [ ] Stateless API workers; session/HITL in durable checkpointer
- [ ] Logs to stdout (structured); Langfuse for spans with redacted args
- [ ] Admin tasks (migrate, seed, eval) as one-off release steps — not agent tools
- [ ] Dependencies pinned; CI gate before run (`make ci-native` or equivalent)

### Testing & rollout
- [ ] End-to-end workflow tests including tool calls
- [ ] Adversarial / disallowed-action tests verify blocks work
- [ ] SOP error-path tests verify halt-and-notify (no recursive troubleshooting)
- [ ] Multi-agent integration tests
- [ ] Langfuse eval datasets for regression on tool selection and policy adherence
- [ ] Gradual rollout with production monitoring and alerts

### Testing & analysis
- [ ] Agent changes covered by `tests/agent/` (mock LLM; assert routing, HITL, allowlist)
- [ ] Static analysis on agent module: ruff, mypy, import-linter ([python-code-analysis](../python-code-analysis/SKILL.md))
- [ ] Security/hardening tests if auth or write paths changed

### End users
- [ ] Transparency copy in product
- [ ] Training or in-app guidance for oversight
- [ ] Human review required before consequential decisions

---

## Anti-patterns

| Anti-pattern | IMDA-aligned fix |
|--------------|------------------|
| "Don't use tool X" in system prompt only | Remove tool from `ToolNode` or block in governance node |
| Approve after irreversible action | `interrupt` before execute |
| One graph with every tool | Split by function; supervisor pattern |
| Rubber-stamp approvals | Audit overrides; require justification for high-risk |
| Prompt-only external agent guardrails | Human vetting, curated memory, allow/deny rules on MCP |
| Storing secrets in graph state | TEE/user takeover for sensitive input; keep secrets out of checkpoints |
| Unredacted PII in Langfuse traces | Redact before span export; shorten retention for sensitive traces |
| Agent retries failed tools indefinitely | SOP halt-and-notify; bounded retries with escalation |
| Direct prod deploy from agent output | Write to `/output` sandbox; HITL before promote |
| Secrets or feature flags baked into prompts | `Settings` / env vars; validate production config at startup |
| Dev-only graph fork for "easier testing" | Same graph; `AGENT_MOCK_LLM` and stub backends via config |
| HITL tied to one server instance | Durable checkpointer + `thread_id`; resume on any worker |

---

## Additional resources

- [reference.md](reference.md) — risk factors, multi-agent risks, Twelve-Factor mapping, related frameworks (CSA, GovTech ARCF, OWASP Agentic AI)
- [Twelve-Factor App](https://12factor.net/) — cloud-native operational baseline
- [python-code-analysis/SKILL.md](../python-code-analysis/SKILL.md) — static & dynamic analysis for Python (pytest, ruff, mypy, import-linter)
- [security-and-hardening.md](../../rules/generic/security-and-hardening.md) — app security patterns (injection, auth, PII)
- IMDA MGF for Agentic AI (v1.5): https://www.imda.gov.sg/-/media/imda/files/about/emerging-tech-and-research/artificial-intelligence/mgf-for-agentic-ai.pdf
- LangGraph interrupts: https://docs.langchain.com/oss/python/langgraph/interrupts
- LangGraph persistence: https://docs.langchain.com/oss/python/langgraph/persistence
- Langfuse LangChain integration: https://langfuse.com/docs/integrations/langchain
- Langfuse Python SDK (`@observe`, scores, datasets): https://langfuse.com/docs/sdk/python
