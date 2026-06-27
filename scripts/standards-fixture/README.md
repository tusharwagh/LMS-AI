# Standards fixture — Phase 1 mechanics lab

Local proof of `manifest` + profiles + `check-standards` + copy materialization before the separate template repo.

## Layout

```text
scripts/standards-fixture/
├── profiles/{core,python,agentic,frontend}/profile.yaml
├── reference/              # synced from .cursor (run sync-reference.sh)
├── manifest.json           # built by build-manifest.py
├── sync-reference.sh
├── build-manifest.py
├── test-standards-fixture.sh
└── TEST-RESULTS.md         # written by test suite
```

Repo-root fixture config:

- `.standards-version.fixture` — pinned version (`fixture-0.1.0`)
- `.standards-latest.fixture` — latest available (bump for stale tests)
- `.standards-profiles.fixture` — comma-separated enabled profiles

## Commands

```bash
# Refresh reference snapshot + manifest
make standards-sync-fixture

# Drift check (warn exit code 2 if findings)
make check-standards-fixture

# Copy reference → .cursor managed paths
make standards-materialize-fixture
make standards-materialize-fixture DRY_RUN=1

# Full T1–T10 suite
make test-standards-fixture
```

## Test scenarios (T1–T10)

| ID | Scenario | Expected |
|----|----------|----------|
| T1 | Copies match reference @ pin | `status: clean`, exit 0 |
| T2 | Latest > pinned | `type: stale`, exit 2 |
| T3 | Edit managed generic copy | `type: diverged`, exit 2 |
| T4 | Delete managed copy | `type: missing`, exit 2 |
| T5 | Edit lms-ai overlay | no overlay findings |
| T6 | Profiles = `core` only | python paths not checked |
| T7 | Diverged generic | `classification: contribution_candidate` |
| T8 | Materialize in test workspace | all profile files present |
| T9 | Re-materialize after drift | clean |
| T10 | `.env` | not in manifest |

## Profile membership

| Asset | Profile(s) |
|-------|------------|
| `ai-sdlc` templates + rules | `core` |
| `code-simplification`, `doubt-driven-development` | `core` |
| `security`, `api`, `sonarqube` rules | `python` |
| `clean-code-ddd-python`, `python-code-analysis` skills | `python` |
| `imda-agentic-ai-governance` skill | `agentic` |
| `frontend-ui-engineering` rule | `frontend` |

See [template-standards-plan.md](../../docs/template-standards-plan.md) Phase 1 exit criteria.
