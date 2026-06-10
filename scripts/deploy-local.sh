#!/usr/bin/env bash
# Local deployment: Docker Compose (db + api + migrations on startup).
# Optional: SEED=1 ./scripts/deploy-local.sh  or  make deploy-local SEED=1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

docker compose up --build -d

API_PORT="${LMS_API_PORT:-8000}"

if [[ "${SEED:-0}" == "1" ]]; then
  echo "Waiting for database before seed..."
  make ensure-venv
  .venv/bin/alembic upgrade head
  .venv/bin/python scripts/seed_sample_data.py
fi

echo ""
echo "LMS-AI local deployment started."
echo "  Health: http://localhost:${API_PORT}/health"
echo "  Docs:   http://localhost:${API_PORT}/docs"
echo "  Logs:   docker compose logs -f api"
echo "  Stop:   make deploy-local-down"
echo "  Destroy: make deploy-destroy"
