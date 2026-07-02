# Runbook — fix diverged managed standards

**When:** `make check-standards` or CI reports `"type": "diverged"` on a path under `.cursor/rules/generic/`, `.cursor/skills/generic/`, or `.cursor/templates/ai-sdlc/`.

**Policy:** LMS-AI uses `.standards-ci-policy` = `fail`. Unmanaged edits to generic copies **block CI**. Stale pin and missing files still **warn only**.

---

## 1. Confirm the finding

```bash
make check-standards
```

Look for `"type": "diverged"` and `"classification": "contribution_candidate"` in the JSON report.

---

## 2. Choose a fix path

| Situation | Action |
|-----------|--------|
| Accidental local edit | **Revert** the managed copy (see §3) |
| Product-specific convention | **Overlay** — move content to `.cursor/rules/lms-ai/` or `.cursor/skills/lms-ai/` |
| Generic improvement for all repos | **Upstream** — contribution issue → template PR → `make standards-upgrade` |

Do **not** leave diverged managed copies in long-lived branches.

---

## 3. Revert (accidental edit)

```bash
git checkout -- .cursor/rules/generic/<file>.md
# or restore from materialize:
make standards-materialize
make check-standards   # should be clean
```

---

## 4. Overlay (product-specific)

1. Copy your change into a new or existing file under `.cursor/rules/lms-ai/` or `.cursor/skills/lms-ai/`.
2. Revert the managed generic file (§3).
3. `make check-standards` — overlay paths are never drift-checked.

---

## 5. Upstream (generic improvement)

```bash
make standards-contribute              # issue body from drift report
make standards-contribute OPEN=1       # open GitHub issue (gh auth)
```

Template owner merges → tags release → in LMS-AI:

```bash
make standards-upgrade VERSION=X.Y.Z
make check-standards
```

See [CONTRIBUTING.md](https://github.com/tusharwagh/org-ai-standards/blob/main/CONTRIBUTING.md).

---

## 6. CI behavior (Phase 5)

| Finding | CI result |
|---------|-----------|
| `diverged` | **Fail** (exit 1) |
| `stale` | Warn (exit 2, job continues) |
| `missing` | Warn (exit 2, job continues) |
| `pin_mismatch` | Warn (exit 2, job continues) |

Config: `.standards-ci-policy` (`fail` | `warn`).

---

## 7. Verify locally

```bash
make verify-phase5
```

---

## Related

- [template-standards/README.md](README.md) — ops hub
- [PHASE5-RESULTS.md](PHASE5-RESULTS.md) — verification record
- [standards/GOVERNANCE.md](../../standards/GOVERNANCE.md) §6–§7
