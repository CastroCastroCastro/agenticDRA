"""Upsert a local dev machine row (127.0.0.1 + DRA gRPC port) for connect checks."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import psycopg

from agent.constants import DEFAULT_DRA_GRPC_PORT
from agent.database.postgres import POSTGRES_CREATE_MACHINES_TABLE_SQL
from agent.env import get_metadata_dsn


def main() -> int:
    port = int(os.environ.get("DRA_DEV_GRPC_PORT", str(DEFAULT_DRA_GRPC_PORT)))
    name = os.environ.get("DEV_MACHINE_NAME", "dev-local")
    dsn = get_metadata_dsn()
    ports_json = json.dumps([port])

    sql = """
INSERT INTO machines (machine_name, IP, Ports, cores, memory_gb, in_use)
VALUES (%s, %s, %s::jsonb, %s, %s, %s)
ON CONFLICT (machine_name) DO UPDATE SET
  IP = EXCLUDED.IP,
  Ports = EXCLUDED.Ports,
  cores = EXCLUDED.cores,
  memory_gb = EXCLUDED.memory_gb,
  in_use = EXCLUDED.in_use;
"""

    with psycopg.connect(dsn) as conn:
        with conn.cursor() as cur:
            cur.execute(POSTGRES_CREATE_MACHINES_TABLE_SQL)
            cur.execute(
                sql,
                (name, "127.0.0.1", ports_json, 4, 16, False),
            )
        conn.commit()

    print(f"Seeded machine '{name}' -> 127.0.0.1:{port} (start server: python3 agent/run_dra_server.py)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
