# Template standards — LMS-AI

How this repo consumes [org-ai-standards](https://github.com/tusharwagh/org-ai-standards).

## Quick reference

| Item | Location |
|------|----------|
| Submodule (reference @ tag) | `standards/` |
| Pin | `.standards-version` |
| CI policy | `.standards-ci-policy` (`fail` — diverged blocks CI) |
| Enabled profiles | `.standards-profiles` (`core,python,agentic,frontend`) |
| Managed copies | `.cursor/rules/generic/`, `.cursor/skills/generic/`, `.cursor/templates/ai-sdlc/` |
| Project overlay | `.cursor/rules/lms-ai/`, `.cursor/skills/lms-ai/` |
| Instantiated governance | `docs/ai-sdlc/CHARTER.md`, `CHANGELOG.md` |

## Commands

```bash
git submodule update --init standards
make standards-materialize
make check-standards
make standards-upgrade VERSION=1.1.3   # after template release is on GitHub
make standards-contribute
make verify-standards-ci              # optional regression (fail-mode policy)
```

## Rules

- **Do not edit** managed generic copies — use `.cursor/rules/lms-ai/` overlay or upstream PR to [org-ai-standards](https://github.com/tusharwagh/org-ai-standards), then `make standards-upgrade`.
- **Template owner** cuts releases; **repository maintainers** bump pin via PR ([standards/GOVERNANCE.md](../../standards/GOVERNANCE.md) §5).
- **Diverged managed paths** — see [RUNBOOK-DIVERGED.md](RUNBOOK-DIVERGED.md).

## CI

`.gitmodules` must use **HTTPS** for `standards/`. Workflow: `.github/workflows/ci.yml` — `submodules: recursive`, `check-standards` fails on diverged.

**Release order:** push template repo (`git push origin main --tags`) **before** LMS-AI bumps the submodule pointer. See [RELEASE.md](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/RELEASE.md).

### `not our ref <sha>` on submodule checkout

Template commit not on GitHub yet — push `org-ai-standards` tags, then re-run CI.

## Template repo docs (canonical)

| Doc | Purpose |
|-----|---------|
| [GOVERNANCE.md](https://github.com/tusharwagh/org-ai-standards/blob/main/GOVERNANCE.md) | Roles, contributions, semver |
| [CONTRIBUTING.md](https://github.com/tusharwagh/org-ai-standards/blob/main/CONTRIBUTING.md) | Contribution loop |
| [docs/SPEC.md](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/SPEC.md) | Full specification |
| [docs/ROLLOUT.md](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/ROLLOUT.md) | Phased rollout (complete) |
| [docs/PHASE6-RESULTS.md](https://github.com/tusharwagh/org-ai-standards/blob/main/docs/PHASE6-RESULTS.md) | Scale-out + `standards-init` |

Rollout Phases 0–6 are **complete**. Spec and plan moved from LMS-AI to org-ai-standards (Jun 2026 cleanup).
