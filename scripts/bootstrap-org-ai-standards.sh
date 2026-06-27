#!/usr/bin/env bash
# Build org-ai-standards template repository from Phase 1 fixture (Phase 2).
set -euo pipefail

LMS_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="${1:-$LMS_ROOT/../org-ai-standards}"
FIXTURE="$LMS_ROOT/scripts/standards-fixture"
VERSION="${2:-1.0.0}"

cd "$LMS_ROOT"
chmod +x scripts/standards-fixture/sync-reference.sh
./scripts/standards-fixture/sync-reference.sh "fixture-$VERSION"

echo "Creating template repo at $TARGET"
rm -rf "$TARGET"
mkdir -p "$TARGET"/{scripts,bootstrap,contributions/inbox,contributions/decisions,profiles}

# Canonical content from fixture reference
cp -R "$FIXTURE/reference/cursor" "$TARGET/"
cp -R "$FIXTURE/reference/docs" "$TARGET/"
cp -R "$FIXTURE/profiles/"* "$TARGET/profiles/"

printf '%s\n' "$VERSION" > "$TARGET/VERSION"

# Promote scripts
cp "$LMS_ROOT/scripts/check-standards.sh" "$TARGET/scripts/check-standards.sh"
cp "$LMS_ROOT/scripts/standards-materialize.sh" "$TARGET/bootstrap/standards-materialize.sh"

cat > "$TARGET/scripts/build-manifest.py" <<'PYEOF'
#!/usr/bin/env python3
"""Expand profile indexes into manifest.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def parse_includes(profile_path: Path) -> list[str]:
    includes: list[str] = []
    in_includes = False
    for line in profile_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped == "includes:":
            in_includes = True
            continue
        if in_includes and stripped.startswith("- "):
            includes.append(stripped[2:].strip())
        elif in_includes and not stripped.startswith("- "):
            break
    return includes


def materialize_to(reference_path: str) -> str:
    if reference_path.startswith("docs/ai-sdlc/templates/"):
        suffix = reference_path.removeprefix("docs/ai-sdlc/templates/")
        return f".cursor/templates/ai-sdlc/{suffix}"
    if reference_path.startswith("cursor/"):
        return f".cursor/{reference_path.removeprefix('cursor/')}"
    return reference_path


def expand_pattern(reference_root: Path, pattern: str) -> list[Path]:
    if pattern.endswith("/**"):
        base = pattern[:-3]
        root = reference_root / base
        if not root.exists():
            return []
        return sorted(p for p in root.rglob("*") if p.is_file())
    path = reference_root / pattern
    if path.is_file():
        return [path]
    return []


def main() -> int:
    reference_root = repo_root()
    profiles_dir = reference_root / "profiles"

    entries: list[dict] = []
    seen: set[str] = set()

    for profile_path in sorted(profiles_dir.glob("*/profile.yaml")):
        profile_name = profile_path.parent.name
        for pattern in parse_includes(profile_path):
            for abs_path in expand_pattern(reference_root, pattern):
                rel = abs_path.relative_to(reference_root).as_posix()
                if rel in seen:
                    for entry in entries:
                        if entry["reference"] == rel and profile_name not in entry["profiles"]:
                            entry["profiles"].append(profile_name)
                    continue
                seen.add(rel)
                entries.append(
                    {
                        "id": rel.replace("/", "__"),
                        "reference": rel,
                        "materialize_to": materialize_to(rel),
                        "profiles": [profile_name],
                    }
                )

    for entry in entries:
        entry["profiles"] = sorted(entry["profiles"])

    manifest = {
        "version": 1,
        "never_manage": [".env", ".env.*"],
        "never_compare": [
            ".cursor/rules/lms-ai/**",
            ".cursor/skills/lms-ai/**",
            "docs/ai-sdlc/CHARTER.md",
            "docs/ai-sdlc/CHANGELOG.md",
            "docs/ai-sdlc/TRACEABILITY.md",
        ],
        "entries": sorted(entries, key=lambda e: e["reference"]),
    }

    out = reference_root / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
PYEOF
chmod +x "$TARGET/scripts/build-manifest.py"

python3 "$TARGET/scripts/build-manifest.py"

# Adapt check-standards defaults for template repo layout
python3 <<PY
from pathlib import Path
path = Path("$TARGET/scripts/check-standards.sh")
text = path.read_text(encoding="utf-8")
text = text.replace(
    'REFERENCE="\${STANDARDS_REFERENCE:-scripts/standards-fixture/reference}"',
    'REFERENCE="\${STANDARDS_REFERENCE:-.}"',
)
text = text.replace(
    'MANIFEST="\${STANDARDS_MANIFEST:-scripts/standards-fixture/manifest.json}"',
    'MANIFEST="\${STANDARDS_MANIFEST:-manifest.json}"',
)
text = text.replace(
    'VERSION_FILE="\${STANDARDS_VERSION_FILE:-.standards-version.fixture}"',
    'VERSION_FILE="\${STANDARDS_VERSION_FILE:-.standards-version}"',
)
text = text.replace(
    'LATEST_FILE="\${STANDARDS_LATEST_FILE:-.standards-latest.fixture}"',
    'LATEST_FILE="\${STANDARDS_LATEST_FILE:-.standards-latest}"',
)
text = text.replace(
    'PROFILES_FILE="\${STANDARDS_PROFILES_FILE:-.standards-profiles.fixture}"',
    'PROFILES_FILE="\${STANDARDS_PROFILES_FILE:-.standards-profiles}"',
)
text = text.replace('"project": "lms-ai"', '"project": "org-ai-standards"')
text = text.replace(
    "Reference file missing in fixture tree",
    "Reference file missing in template tree",
)
path.write_text(text, encoding="utf-8")
PY

python3 <<PY
from pathlib import Path
path = Path("$TARGET/bootstrap/standards-materialize.sh")
text = path.read_text(encoding="utf-8")
text = text.replace(
    'MANIFEST="\${STANDARDS_MANIFEST:-scripts/standards-fixture/manifest.json}"',
    'MANIFEST="\${STANDARDS_MANIFEST:-manifest.json}"',
)
text = text.replace(
    'PROFILES_FILE="\${STANDARDS_PROFILES_FILE:-.standards-profiles.fixture}"',
    'PROFILES_FILE="\${STANDARDS_PROFILES_FILE:-.standards-profiles}"',
)
text = text.replace(
    'REFERENCE="\${STANDARDS_REFERENCE:-scripts/standards-fixture/reference}"',
    'REFERENCE="\${STANDARDS_REFERENCE:-.}"',
)
path.write_text(text, encoding="utf-8")
PY

# Traceability script from ai-sdlc templates
cp "$TARGET/docs/ai-sdlc/templates/github/check_pr_traceability.sh" "$TARGET/scripts/check_pr_traceability.sh"
chmod +x "$TARGET/scripts/"*.sh "$TARGET/bootstrap/"*.sh

# Product-repo example config
printf '%s\n' "$VERSION" > "$TARGET/.standards-version.example"
printf '%s\n' "$VERSION" > "$TARGET/.standards-latest.example"
printf 'core,python,agentic,frontend\n' > "$TARGET/.standards-profiles.example"

# GOVERNANCE (paths adjusted for template repo root)
LMS_ROOT="$LMS_ROOT" TARGET="$TARGET" python3 <<'PY'
import os
from pathlib import Path
lms = Path(os.environ["LMS_ROOT"])
target = Path(os.environ["TARGET"])
src = (lms / "docs/template-standards/GOVERNANCE.md").read_text(encoding="utf-8")
src = src.replace(
    "This document will move to the future `org-ai-standards` template repository. Until then it lives in LMS-AI as the authoritative governance draft.",
    "Authoritative governance for the **org-ai-standards** delivery template repository.",
)
src = src.replace("../template-standards-research.md", "docs/SPEC-LINK.md")
src = src.replace("../template-standards-plan.md", "docs/PLAN-LINK.md")
src = src.replace("[CHARTER](../ai-sdlc/CHARTER.md)", "project docs/ai-sdlc/CHARTER.md (instantiated per repo)")
src = src.replace("[CHARTER.md](../ai-sdlc/CHARTER.md)", "project CHARTER (instantiated)")
src = src.replace("*Promote this file to the template repo root as `GOVERNANCE.md` in Phase 2.*", "")
(target / "GOVERNANCE.md").write_text(src, encoding="utf-8")
PY

cat > "$TARGET/README.md" <<EOF
# org-ai-standards

Delivery template for AI-assisted repositories — generic Cursor rules/skills, AI-SDLC bootstrap assets, profiles, and drift checking.

**Release:** v$VERSION (semver tag \`v$VERSION\`)  
**Governance:** [GOVERNANCE.md](GOVERNANCE.md)

## Profiles

| Profile | Purpose |
|---------|---------|
| \`core\` | AI-SDLC templates, traceability assets, core rules (required) |
| \`python\` | Python / FastAPI engineering rules and skills |
| \`agentic\` | LLM / agent governance skill |
| \`frontend\` | Frontend UI engineering rule |

Example: \`core,python,agentic,frontend\`

## Product repo bootstrap (Phase 3+)

\`\`\`bash
# Add submodule @ tag
git submodule add -b v$VERSION <REPO_URL> standards
git submodule update --init --recursive

# Pin and profiles (copy examples to repo root)
cp standards/.standards-version.example .standards-version
cp standards/.standards-latest.example .standards-latest
cp standards/.standards-profiles.example .standards-profiles

# Materialize managed copies into .cursor/
standards/bootstrap/standards-materialize.sh

# Drift check
standards/scripts/check-standards.sh
\`\`\`

## Template repo self-check

\`\`\`bash
cp .standards-version.example .standards-version
cp .standards-latest.example .standards-latest
cp .standards-profiles.example .standards-profiles
./bootstrap/verify-template.sh
\`\`\`

## Layout

\`\`\`text
cursor/rules/generic/       # canonical Cursor rules
cursor/skills/generic/      # canonical skills
docs/ai-sdlc/templates/   # AI-SDLC bootstrap templates
profiles/                   # profile indexes
manifest.json               # managed paths
scripts/                    # check-standards, build-manifest
bootstrap/                  # materialize, verify
\`\`\`

See LMS-AI [template-standards-plan.md](https://github.com/) for rollout phases.
EOF

cat > "$TARGET/CHANGELOG.md" <<EOF
# Changelog

All notable template releases use [semver](https://semver.org/).

## [1.0.0] - 2026-06-27

### Added

- Initial delivery template extracted from LMS-AI Phase 1 fixture
- Profiles: \`core\`, \`python\`, \`agentic\`, \`frontend\`
- \`manifest.json\` with $(python3 -c "import json; print(len(json.load(open('$TARGET/manifest.json'))['entries']))") managed paths
- \`scripts/check-standards.sh\` and \`bootstrap/standards-materialize.sh\`
- AI-SDLC bootstrap templates under \`docs/ai-sdlc/templates/\`
- Generic Cursor rules and skills (portable layer)
- [GOVERNANCE.md](GOVERNANCE.md)

### Deferred (Minimal v1)

- \`docs/standards/\` portable doc extraction
- Org-level profiles
- Fail-mode CI defaults
EOF

cat > "$TARGET/bootstrap/verify-template.sh" <<'EOF'
#!/usr/bin/env bash
# Phase 2 verification: materialize + check-standards in template repo (V2.1).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cp -f .standards-version.example .standards-version
cp -f .standards-latest.example .standards-latest
cp -f .standards-profiles.example .standards-profiles

chmod +x bootstrap/standards-materialize.sh scripts/check-standards.sh
STANDARDS_ROOT="$ROOT" STANDARDS_REFERENCE="." ./bootstrap/standards-materialize.sh

if STANDARDS_ROOT="$ROOT" STANDARDS_REFERENCE="." ./scripts/check-standards.sh | python3 -c '
import json, sys
r = json.load(sys.stdin)
assert r["status"] == "clean", r
print("verify-template: clean")
'; then
  exit 0
fi
exit 1
EOF
chmod +x "$TARGET/bootstrap/verify-template.sh"

cat > "$TARGET/.gitignore" <<'EOF'
.cursor/
.standards-version
.standards-latest
.standards-profiles
EOF

cat > "$TARGET/scripts/verify-phase2.sh" <<'EOF'
#!/usr/bin/env bash
# V2.1–V2.5 checks for Phase 2 exit criteria.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
FAIL=0

log() { printf '%s\n' "$*"; }
pass() { log "PASS  $1"; }
fail() { log "FAIL  $1"; FAIL=1; }

log "=== V2.1 self-check ==="
if ./bootstrap/verify-template.sh; then pass "V2.1"; else fail "V2.1"; fi

log "=== V2.2 tag / manifest ==="
ENTRIES=$(python3 -c "import json; print(len(json.load(open('manifest.json'))['entries']))")
if [[ "$ENTRIES" -ge 26 ]]; then pass "V2.2 manifest ($ENTRIES entries)"; else fail "V2.2"; fi

log "=== V2.3 file count ==="
COUNT=$(find cursor docs/ai-sdlc/templates profiles -type f | wc -l | tr -d ' ')
if [[ "$COUNT" -ge 26 ]]; then pass "V2.3 canonical files ($COUNT)"; else fail "V2.3"; fi

log "=== V2.4 domain spot-check ==="
if grep -r "K-12 library management monolith" cursor/ docs/ai-sdlc/templates/*.template.md 2>/dev/null; then
  fail "V2.4 LMS domain text in generic/template paths"
else
  pass "V2.4 no LMS domain in generic paths"
fi

log "=== V2.5 shellcheck ==="
if command -v shellcheck >/dev/null 2>&1; then
  if shellcheck scripts/*.sh bootstrap/*.sh; then pass "V2.5 shellcheck"; else fail "V2.5"; fi
else
  pass "V2.5 shellcheck skipped (not installed)"
fi

exit "$FAIL"
EOF
chmod +x "$TARGET/scripts/verify-phase2.sh"

# Git init + tag
if git -C "$TARGET" rev-parse --git-dir >/dev/null 2>&1; then
  rm -rf "$TARGET/.git"
fi
git -C "$TARGET" init -b main
git -C "$TARGET" add -A
git -C "$TARGET" \
  -c user.email="standards-template@local" \
  -c user.name="org-ai-standards bootstrap" \
  commit -m "$(cat <<EOF
feat: initial org-ai-standards template v$VERSION

Extract delivery template from LMS-AI Phase 1 fixture.
Profiles: core, python, agentic, frontend.
Includes check-standards, materialize, manifest, GOVERNANCE.

EOF
)"
git -C "$TARGET" \
  -c user.email="standards-template@local" \
  -c user.name="org-ai-standards bootstrap" \
  tag -a "v$VERSION" -m "org-ai-standards v$VERSION"

echo ""
echo "Template repo ready: $TARGET"
echo "Running Phase 2 verification..."
"$TARGET/scripts/verify-phase2.sh"
