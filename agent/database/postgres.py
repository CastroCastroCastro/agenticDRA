"""PostgreSQL helpers for machine metadata."""

from __future__ import annotations

import importlib
from typing import Any


# TODO: replace these placeholders in deployment config.
POSTGRES_HOST = "TODO"
POSTGRES_PORT = "TODO"
POSTGRES_DATABASE = "TODO"
POSTGRES_USER = "TODO"
POSTGRES_PASSWORD = "TODO"
DEFAULT_POSTGRES_DSN = (
    f"postgresql://{POSTGRES_USER}:{POSTGRES_PASSWORD}@"
    f"{POSTGRES_HOST}:{POSTGRES_PORT}/{POSTGRES_DATABASE}"
)

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
    """Load psycopg lazily so local tooling can run without Postgres driver."""
    try:
        return importlib.import_module("psycopg")
    except ImportError as exc:
        raise ImportError(
            "psycopg is required for PostgreSQL. Install it with 'pip install psycopg[binary]'"
        ) from exc


def _validate_dsn(dsn: str) -> None:
    """Fail fast for unresolved placeholder DSN values."""
    if "TODO" in dsn:
        raise ValueError("PostgreSQL DSN has TODO placeholders; set METADATA_DB_URL to a real value")


def _ensure_schema(cursor: Any) -> None:
    """Create machine table if missing."""
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


def reserve_machine(dsn: str, machine_name: str) -> bool:
    """Reserve machine operation hook.

    TODO: implement atomic machine reservation.
    """
    raise NotImplementedError("TODO: implement reserve_machine")


def release_machine(dsn: str, machine_name: str) -> bool:
    """Release machine operation hook.

    TODO: implement machine release behavior.
    """
    raise NotImplementedError("TODO: implement release_machine")


def delete_machine(dsn: str, machine_name: str) -> bool:
    """Delete machine operation hook.

    TODO: implement machine deletion behavior.
    """
    raise NotImplementedError("TODO: implement delete_machine")


def update_machine(
    dsn: str,
    machine_name: str,
    ip: str | None = None,
    ports: list[int] | None = None,
    cores: int | None = None,
    memory_gb: int | None = None,
    in_use: bool | None = None,
) -> None:
    """Update machine fields operation hook.

    TODO: implement partial update behavior for provided non-None fields.
    """
    raise NotImplementedError("TODO: implement update_machine")
