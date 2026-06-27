#!/usr/bin/env bash
# Snapshot current LMS-AI generic Cursor assets into the fixture reference tree.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
REF="$ROOT/scripts/standards-fixture/reference"
VERSION="${1:-fixture-0.1.0}"

cd "$ROOT"

rm -rf "$REF/cursor" "$REF/docs"
mkdir -p "$REF/cursor/rules/generic" "$REF/cursor/skills/generic" "$REF/docs/ai-sdlc/templates"

cp -R .cursor/rules/generic/. "$REF/cursor/rules/generic/"
cp -R .cursor/skills/generic/. "$REF/cursor/skills/generic/"
cp -R .cursor/templates/ai-sdlc/. "$REF/docs/ai-sdlc/templates/"
cp -R scripts/standards-fixture/profiles "$REF/profiles"

printf '%s\n' "$VERSION" > "$REF/VERSION"

python3 "$ROOT/scripts/standards-fixture/build-manifest.py"
echo "Reference synced @ $VERSION"
