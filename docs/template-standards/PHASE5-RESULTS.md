# Phase 5 results — fail mode (LMS-AI)

**Date:** 2026-06-27  
**Status:** Complete

## Goal

Unmanaged divergence on **managed generic copies** fails CI; stale/missing remain warn-only.

## Deliverables

| # | Deliverable | Location |
|---|-------------|----------|
| 5.1 | `ci_policy: fail` for diverged | `.standards-ci-policy` → `Makefile` `STANDARDS_ENV` |
| 5.2 | CI blocking on diverged | `.github/workflows/ci.yml` |
| 5.3 | Stale/missing warn only | `check-standards.sh` exit 2 (unchanged semantics) |
| 5.4 | Runbook | [RUNBOOK-DIVERGED.md](RUNBOOK-DIVERGED.md) |

## Verification

| ID | Check | Result |
|----|-------|--------|
| V5.1 | Intentional generic edit fails `make check-standards` | Pass (`verify-phase5`) |
| V5.2 | Overlay-only edit passes | Pass |
| V5.3 | Revert restores clean | Pass |

```bash
make verify-phase5
```

## CI policy matrix

| `.standards-ci-policy` | `diverged` | `stale` / `missing` |
|------------------------|------------|---------------------|
| `fail` (LMS-AI default) | exit 1 — **blocks** | exit 2 — warn |
| `warn` (legacy / Phase 3–4) | exit 2 — warn | exit 2 — warn |

`make ci-native` now includes `check-standards` so local parity matches CI.

## Next

Phase 6 — scale-out (second product repo).
