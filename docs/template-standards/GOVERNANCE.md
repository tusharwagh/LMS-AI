# Template standards — governance (v1)

**Status:** Active (Phase 0 — Jun 2026)  
**Scope:** Delivery template (`core`, `python`, `agentic`, `frontend`) for AI-assisted repos  
**Spec:** [template-standards-research.md](../template-standards-research.md)  
**Plan:** [template-standards-plan.md](../template-standards-plan.md)  
**Template repo:** [org-ai-standards](https://github.com/tusharwagh/org-ai-standards) (submodule at `standards/`)

Governance for delivery standards. The canonical copy also lives in the template repo [GOVERNANCE.md](https://github.com/tusharwagh/org-ai-standards/blob/main/GOVERNANCE.md). This file tracks LMS-AI-specific notes during rollout.

---

## 1. Roles

| Role | Who (v1) | Responsibilities |
|------|----------|------------------|
| **Template owner** | Repository maintainers | Approve changes to generic standards; cut semver tags; triage contributions; own `manifest.json` and profiles |
| **Project maintainer** | Repository maintainers (LMS-AI) | Pin bump and `standards upgrade` in product repos via PR; own project overlays |
| **Contributor** | Any engineer | Propose improvements via template PR or contribution issue; fix drift via overlay or upstream |
| **Auditor / reviewer** | Humans per CHARTER | Read `docs/standards/` (future) and `docs/ai-sdlc/CHARTER.md`; no Cursor required |

---

## 2. Standards tiers (v1)

| Tier | v1 handling | Drift-checked? |
|------|-------------|----------------|
| **Delivery** | Template repo — profiles `core`, `python`, `agentic`, `frontend` | Yes (managed copies) |
| **Business / architecture / technology (org)** | **Option D** — linked from [CHARTER](../ai-sdlc/CHARTER.md) and project docs; not in template machinery until v1.1 | No (v1) |

Org-level profiles (`org-architecture`, `org-technology`, `org-business`) are deferred to **v1.1** (research §15.2 Option A or C).

---

## 3. v1 package

**Chosen: Minimal** (research §15.8)

| In scope for v1 | Deferred |
|-----------------|----------|
| Submodule @ tag + copy materialization | `docs/standards/` extraction (fat rules OK) |
| `check-standards` warn-only in CI | Fail mode on diverged (Phase 5) |
| Four delivery profiles | Org profiles, waivers |
| GitHub issues for contributions | Committed `contributions/inbox/` YAML |
| Governance doc (this file) | Automated bootstrap scripts (manual OK for pilot) |

---

## 4. Change authority

### 4.1 Template repo (generic standards)

1. Change proposed via **PR** to template repo (or LMS-AI fixture during Phase 1).
2. **Template owner** reviews and merges.
3. **Template owner** cuts semver tag and updates `CHANGELOG.md`.
4. Product repos remain on old pin until maintainers run upgrade (§5).

**Semver:**

| Bump | When |
|------|------|
| **MAJOR** | Removed or renamed managed paths; breaking manifest change |
| **MINOR** | New files, profiles, or backward-compatible standards |
| **PATCH** | Typos, clarifications, non-normative fixes |

### 4.2 Product repo (LMS-AI overlays)

| Path | Who edits | Drift check |
|------|-----------|-------------|
| `.cursor/rules/lms-ai/`, `.cursor/skills/lms-ai/` | Project maintainers | Excluded |
| `docs/ai-sdlc/CHARTER.md`, `CHANGELOG.md`, `TRACEABILITY.md` | Project maintainers | Excluded |
| `.cursor/rules/generic/`, `.cursor/skills/generic/` (managed copies) | **Do not edit locally** — overlay or upstream | Compared @ pin |

**Rule:** Unmanaged edits to generic copies are **not allowed** as a long-term practice. Fix by: revert, move to overlay, or upstream PR + upgrade.

---

## 5. Pin bump and upgrade (G4)

| Action | Owner | Process |
|--------|-------|---------|
| Bump `.standards-version` | **Repository maintainers** | PR to LMS-AI; must pass `make check-standards` (warn OK in Phase 3) |
| Run `standards upgrade` / re-materialize | **Repository maintainers** | Same PR; updates submodule pointer and managed copies |
| AI agent executes upgrade | **Blocked** | Human must request explicitly (same as merge/push) |

After upgrade: append entry to [docs/ai-sdlc/CHANGELOG.md](../ai-sdlc/CHANGELOG.md).

**Publish order:** Push [org-ai-standards](https://github.com/tusharwagh/org-ai-standards) (`git push origin main --tags`) **before** committing a new submodule pointer in LMS-AI. See [README.md](README.md#ci-troubleshooting) and template [RELEASE.md](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/RELEASE.md).

---

## 6. Contribution loop (G5)

When a project has a **contribution candidate** (improved generic standard):

```text
check-standards → diverged / contribution_candidate
       │
       ▼
Open GitHub issue on template repo (label: contribution)
       │
       ▼
Template owner: accept → PR + tag  |  reject → close + reason
       │
       ▼
Product repos: standards upgrade on new tag
```

| v1 inbox | Committed YAML inbox |
|----------|----------------------|
| **GitHub issues** on template repo | Deferred |

**Product delivery is not blocked** while a contribution is under review (warn-only until Phase 5 fail mode).

---

## 7. CI policy (preview)

| Phase | Policy |
|-------|--------|
| Phase 3–4 (pilot) | `stale`, `diverged`, `missing` → **warn** |
| Phase 5 | `diverged` on managed paths → **fail** |
| Overlay edits | Never fail |

**Warn → fail trigger (E3):** Manual decision by template owner after LMS-AI completes one successful upgrade cycle (Phase 3 exit). Not time-based for v1.

---

## 8. Escalation (G8)

v1: **No waivers.** Fix diverged paths by revert, overlay, or upstream. Revisit time-boxed `standards-waiver.yaml` if fail mode causes undue friction.

---

## 9. Decision record (Phase 0)

| ID | Decision | Date |
|----|----------|------|
| G1 | Template owner = **repository maintainers** | 2026-06-26 |
| G4 | Pin bump = **repository maintainers via PR** | 2026-06-26 |
| G5 | Contribution inbox = **GitHub issues** | 2026-06-26 |
| G6 | Org tiers v1 = **Option D** (CHARTER links; profiles in v1.1) | 2026-06-26 |
| Package | **Minimal** | 2026-06-26 |
| E3 | Fail mode after Phase 3 exit + owner sign-off | 2026-06-26 |
| C1 | Defer `docs/standards/` extraction to post-v1.0.0 | 2026-06-26 |

---

## 10. Related docs

| Doc | Purpose |
|-----|---------|
| [CHARTER.md](../ai-sdlc/CHARTER.md) | LMS-AI AI-SDLC gates including standards upgrade |
| [template-standards-research.md](../template-standards-research.md) | Full spec |
| [template-standards-plan.md](../template-standards-plan.md) | Phased implementation |
| [template-standards/README.md](README.md) | LMS-AI submodule ops + CI troubleshooting |
| [org-ai-standards RELEASE](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/RELEASE.md) | Push template before bumping submodule |
