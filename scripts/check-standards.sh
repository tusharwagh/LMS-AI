#!/usr/bin/env bash
# Deterministic standards drift check (fixture Phase 1).
set -euo pipefail

ROOT="${STANDARDS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

REFERENCE="${STANDARDS_REFERENCE:-scripts/standards-fixture/reference}"
MANIFEST="${STANDARDS_MANIFEST:-scripts/standards-fixture/manifest.json}"
VERSION_FILE="${STANDARDS_VERSION_FILE:-.standards-version.fixture}"
LATEST_FILE="${STANDARDS_LATEST_FILE:-.standards-latest.fixture}"
PROFILES_FILE="${STANDARDS_PROFILES_FILE:-.standards-profiles.fixture}"
CI_POLICY="${CI_POLICY:-warn}"
REPORT="${STANDARDS_REPORT:-}"

for f in "$MANIFEST" "$VERSION_FILE" "$PROFILES_FILE" "$REFERENCE/VERSION"; do
  if [[ ! -f "$f" ]]; then
    echo "Missing required file: $f" >&2
    exit 1
  fi
done

PINNED="$(tr -d '[:space:]' < "$VERSION_FILE")"
LATEST="$(tr -d '[:space:]' < "$LATEST_FILE")"
REF_VERSION="$(tr -d '[:space:]' < "$REFERENCE/VERSION")"

export ROOT REFERENCE MANIFEST PINNED LATEST REF_VERSION CI_POLICY REPORT PROFILES_FILE
ENABLED_PROFILES_JSON="$(python3 -c "
import json
text=open('$PROFILES_FILE', encoding='utf-8').read()
print(json.dumps([p.strip() for p in text.split(',') if p.strip()]))
")"
export ENABLED_PROFILES_JSON

python3 - <<'PY'
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

root = Path(os.environ["ROOT"])
reference = root / os.environ["REFERENCE"]
manifest = json.loads((root / os.environ["MANIFEST"]).read_text(encoding="utf-8"))
enabled = set(json.loads(os.environ["ENABLED_PROFILES_JSON"]))
pinned = os.environ["PINNED"]
latest = os.environ["LATEST"]
ref_version = os.environ["REF_VERSION"]
ci_policy = os.environ["CI_POLICY"]
report_path = os.environ.get("REPORT", "")

findings: list[dict] = []


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


if pinned != ref_version:
    findings.append(
        {
            "type": "pin_mismatch",
            "message": f".standards-version={pinned} but reference/VERSION={ref_version}",
        }
    )

if latest != pinned:
    findings.append(
        {
            "type": "stale",
            "message": f"Latest {latest} available; project pinned at {pinned}",
        }
    )

for entry in manifest["entries"]:
    profiles = set(entry["profiles"])
    if not enabled.intersection(profiles):
        continue
    ref_path = reference / entry["reference"]
    project_path = root / entry["materialize_to"]
    if not ref_path.is_file():
        findings.append(
            {
                "type": "reference_missing",
                "path": entry["reference"],
                "message": "Reference file missing in fixture tree",
            }
        )
        continue
    if not project_path.is_file():
        findings.append({"type": "missing", "path": entry["materialize_to"], "reference": entry["reference"]})
        continue
    if sha256(ref_path) != sha256(project_path):
        findings.append(
            {
                "type": "diverged",
                "path": entry["materialize_to"],
                "reference": entry["reference"],
                "classification": "contribution_candidate",
            }
        )

never_manage = manifest.get("never_manage", [])
for pattern in never_manage:
    if pattern == ".env" and (root / ".env").exists():
        for entry in manifest["entries"]:
            if entry["materialize_to"] == ".env":
                findings.append({"type": "never_manage_violation", "path": ".env"})
                break

has_diverged = any(f["type"] == "diverged" for f in findings)
has_blocking = has_diverged and ci_policy == "fail"
has_warn = any(f["type"] in {"stale", "diverged", "missing", "pin_mismatch", "reference_missing"} for f in findings)

if not findings:
    status = "clean"
elif has_blocking:
    status = "fail"
elif has_warn:
    status = "warn"
else:
    status = "clean"

report = {
    "project": "lms-ai",
    "standards_version": pinned,
    "reference_version": ref_version,
    "template_latest": latest,
    "profiles": sorted(enabled),
    "status": status,
    "ci_policy": ci_policy,
    "checked_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "findings": findings,
}

text = json.dumps(report, indent=2)
print(text)
if report_path:
    Path(report_path).write_text(text + "\n", encoding="utf-8")

if status == "clean":
    sys.exit(0)
if status == "fail":
    sys.exit(1)
sys.exit(2)
PY
