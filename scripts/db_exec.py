#!/usr/bin/env python3
"""Run SQL files against DATABASE_URL from .env (psycopg)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from sqlalchemy.engine import make_url  # noqa: E402

from lms.config import get_settings  # noqa: E402


def _psycopg_url(database_url: str, *, database: str | None = None) -> str:
    url = make_url(database_url)
    if database is not None:
        url = url.set(database=database)
    return url.render_as_string(hide_password=False).replace(
        "postgresql+psycopg://", "postgresql://"
    )


def run_sql(sql: str, *, database: str | None = None) -> None:
    import psycopg

    settings = get_settings()
    conn_url = _psycopg_url(settings.database_url, database=database)
    with psycopg.connect(conn_url, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute(sql)


def run_sql_file(path: Path, *, database: str | None = None) -> None:
    sql = path.read_text(encoding="utf-8")
    run_sql(sql, database=database)


def parse_database_name(database_url: str) -> str:
    return make_url(database_url).database or "lms"


def main() -> int:
    parser = argparse.ArgumentParser(description="Execute SQL against LMS DATABASE_URL")
    parser.add_argument("sql_file", type=Path, nargs="?", help="Path to .sql file")
    parser.add_argument(
        "--database",
        help="Override target database (default: from DATABASE_URL)",
    )
    parser.add_argument(
        "--maintenance-db",
        default="postgres",
        help="Maintenance DB for admin ops (default: postgres)",
    )
    parser.add_argument(
        "--drop-database",
        action="store_true",
        help="Drop and recreate the application database from DATABASE_URL",
    )
    args = parser.parse_args()

    settings = get_settings()
    app_db = args.database or parse_database_name(settings.database_url)

    try:
        if args.drop_database:
            terminate = f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{app_db}' AND pid <> pg_backend_pid();
            """
            run_sql(terminate, database=args.maintenance_db)
            run_sql(f'DROP DATABASE IF EXISTS "{app_db}";', database=args.maintenance_db)
            run_sql(f'CREATE DATABASE "{app_db}";', database=args.maintenance_db)
            print(f"Dropped and recreated database '{app_db}'.")
            return 0

        if args.sql_file is None:
            parser.error("sql_file is required unless --drop-database is set")

        if not args.sql_file.is_file():
            print(f"SQL file not found: {args.sql_file}", file=sys.stderr)
            return 1

        run_sql_file(args.sql_file, database=app_db)
        print(f"Executed {args.sql_file.name} on database '{app_db}'.")
        return 0
    except Exception as exc:
        print(f"db_exec failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
