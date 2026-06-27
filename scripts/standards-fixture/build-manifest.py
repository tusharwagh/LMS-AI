#!/usr/bin/env python3
"""Expand profile indexes into manifest.json for the standards fixture."""

from __future__ import annotations

import json
import sys
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def fixture_root() -> Path:
    return Path(__file__).resolve().parent


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
    reference_root = fixture_root() / "reference"
    profiles_dir = fixture_root() / "profiles"
    if not reference_root.is_dir():
        print("Reference tree missing. Run scripts/standards-fixture/sync-reference.sh first.", file=sys.stderr)
        return 1

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

    out = fixture_root() / "manifest.json"
    out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out} ({len(entries)} entries)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
