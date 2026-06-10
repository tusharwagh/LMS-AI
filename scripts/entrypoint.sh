#!/bin/sh
set -e

echo "Waiting for database..."
python <<'PY'
import os
import sys
import time

import psycopg

url = os.environ["DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
for attempt in range(60):
    try:
        with psycopg.connect(url):
            print("Database is ready.")
            break
    except Exception as exc:  # noqa: BLE001 — retry until timeout
        if attempt == 59:
            print(f"Database not ready: {exc}", file=sys.stderr)
            sys.exit(1)
        time.sleep(1)
PY

echo "Running migrations..."
alembic upgrade head

echo "Starting API..."
exec uvicorn lms.main:app --host 0.0.0.0 --port 8000
