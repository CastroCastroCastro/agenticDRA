"""PostgreSQL helpers for machine metadata."""

from __future__ import annotations

import importlib
from typing import Any

POSTGRES_CREATE_MACHINES_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS machines (
    machine_name TEXT PRIMARY KEY,
    IP TEXT NOT NULL,
    Ports JSONB NOT NULL,
    cores INTEGER NOT NULL,
    memory_gb INTEGER NOT NULL,
    in_use BOOLEAN NOT NULL
)
"""


def _load_psycopg():
    try:
        return importlib.import_module("psycopg")
    except ImportError as exc:
        raise ImportError(
            "psycopg is required for PostgreSQL. Install it with 'pip install psycopg[binary]'"
        ) from exc


def _validate_dsn(dsn: str) -> None:
    if not dsn or not dsn.strip():
        raise ValueError("PostgreSQL DSN is empty; set METADATA_DB_URL")
    if "TODO" in dsn:
        raise ValueError("PostgreSQL DSN still contains TODO placeholders")


def _ensure_schema(cursor: Any) -> None:
    cursor.execute(POSTGRES_CREATE_MACHINES_TABLE_SQL)


def read_rows_from_postgres(dsn: str, select_sql: str) -> list[tuple[Any, ...]]:
    """Read machine rows from PostgreSQL metadata store."""
    _validate_dsn(dsn)
    psycopg = _load_psycopg()

    with psycopg.connect(dsn) as connection:
        with connection.cursor() as cursor:
            _ensure_schema(cursor)
            connection.commit()
            cursor.execute(select_sql)
            rows = cursor.fetchall()
    return rows
