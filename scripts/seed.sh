#!/usr/bin/env bash
# Load sample data (Python default, or SQL via --sql).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

MODE="${1:-python}"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

make ensure-venv

case "$MODE" in
  python)
    .venv/bin/python -m alembic upgrade head
    .venv/bin/python scripts/seed_sample_data.py
    ;;
  sql)
    .venv/bin/python -m alembic upgrade head
    .venv/bin/python scripts/db_exec.py scripts/sql/002_sample_data.sql
    ;;
  *)
    echo "Usage: $0 [python|sql]" >&2
    exit 1
    ;;
esac
