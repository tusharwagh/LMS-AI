#!/usr/bin/env bash
# Copy managed standards from reference tree into project paths (enabled profiles only).
set -euo pipefail

ROOT="${STANDARDS_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
cd "$ROOT"

REFERENCE="${STANDARDS_REFERENCE:-scripts/standards-fixture/reference}"
MANIFEST="${STANDARDS_MANIFEST:-scripts/standards-fixture/manifest.json}"
PROFILES_FILE="${STANDARDS_PROFILES_FILE:-.standards-profiles.fixture}"
DRY_RUN="${DRY_RUN:-0}"

if [[ ! -f "$MANIFEST" ]]; then
  echo "Manifest not found: $MANIFEST (run sync-reference.sh first)" >&2
  exit 1
fi

export ROOT REFERENCE MANIFEST DRY_RUN PROFILES_FILE
ENABLED_PROFILES_JSON="$(python3 -c "
import json
text=open('$PROFILES_FILE', encoding='utf-8').read()
print(json.dumps([p.strip() for p in text.split(',') if p.strip()]))
")"
export ENABLED_PROFILES_JSON

python3 - <<'PY'
import json
import os
import shutil
import sys
from pathlib import Path

root = Path(os.environ["ROOT"])
reference = root / os.environ["REFERENCE"]
manifest_path = root / os.environ["MANIFEST"]
enabled = set(json.loads(os.environ["ENABLED_PROFILES_JSON"]))
dry_run = os.environ.get("DRY_RUN", "0") == "1"

manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
copied = 0
for entry in manifest["entries"]:
    if not enabled.intersection(entry["profiles"]):
        continue
    src = reference / entry["reference"]
    dst = root / entry["materialize_to"]
    if not src.is_file():
        print(f"skip missing reference: {entry['reference']}", file=sys.stderr)
        continue
    if dry_run:
        print(f"would copy {src.relative_to(root)} -> {entry['materialize_to']}")
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"copied {entry['materialize_to']}")
    copied += 1

print(f"materialize: {copied} file(s)" + (" (dry-run)" if dry_run else ""))
PY
