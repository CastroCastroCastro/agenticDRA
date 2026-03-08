"""Utilities for selecting machines and preparing RPC connectivity."""

from __future__ import annotations

import json
import os
import socket
import threading
from collections.abc import Mapping
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (parent of agent/) so METADATA_DB_URL is set
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from typing import Any
from urllib.parse import urlparse

from database.postgres import DEFAULT_POSTGRES_DSN, read_rows_from_postgres


DEFAULT_TIMEOUT_SECONDS = 1.0

IN_USE_FIELD = "In-use"
REQUIRED_MACHINE_FIELDS = {"IP", "Ports", "cores", "memory_gb", IN_USE_FIELD}

SELECT_MACHINES_SQL = """
SELECT machine_name, IP, Ports, cores, memory_gb, in_use
FROM machines
ORDER BY machine_name
"""

MachineDetails = dict[str, Any]
MachinesMap = dict[str, MachineDetails]


class Script:
    """Load, validate, and query machine metadata for scheduling operations.

    Metadata is read from PostgreSQL only.
    """

    def __init__(self, metadata_db_url: str | None = None):
        self._lock = threading.Lock()
        self._metadata_db_url = self._resolve_metadata_db_url(metadata_db_url)
        self.machines = self._read_machines(self._metadata_db_url)
        self._machines_by_name = self._parse_machines(self.machines)

    def _resolve_metadata_db_url(self, metadata_db_url: str | None) -> str:
        """Resolve metadata connection to a canonical URL.

        Precedence:
        1) explicit ``metadata_db_url`` argument
        2) ``METADATA_DB_URL`` env var
        3) default PostgreSQL DSN
        """
        configured_url = metadata_db_url or os.environ.get("METADATA_DB_URL")
        resolved_url = configured_url or DEFAULT_POSTGRES_DSN
        parsed = urlparse(resolved_url)
        if parsed.scheme not in ("postgresql", "postgres"):
            raise ValueError("METADATA_DB_URL must use postgresql:// or postgres://")
        return resolved_url

    def _read_machines(self, metadata_db_url: str) -> MachinesMap:
        """Read machine metadata rows from PostgreSQL."""
        rows = self._read_rows_from_postgres(metadata_db_url)
        return self._rows_to_machines(rows)

    def _read_rows_from_postgres(self, dsn: str) -> list[tuple[Any, ...]]:
        return read_rows_from_postgres(dsn, SELECT_MACHINES_SQL)

    def _rows_to_machines(self, rows: list[tuple[Any, ...]]) -> MachinesMap:
        if not rows:
            raise ValueError("No machines found in metadata store")

        machines: MachinesMap = {}
        for machine_name, ip, ports_value, cores, memory_gb, in_use in rows:
            ports = self._parse_ports(machine_name, ports_value)
            machines[machine_name] = {
                "IP": ip,
                "Ports": ports,
                "cores": cores,
                "memory_gb": memory_gb,
                IN_USE_FIELD: bool(in_use),
            }
        return machines

    def _parse_ports(self, machine_name: str, ports_value: Any) -> list[int]:
        if isinstance(ports_value, str):
            try:
                ports = json.loads(ports_value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Machine '{machine_name}' has invalid 'Ports' JSON") from exc
        else:
            ports = ports_value

        if not isinstance(ports, list) or not all(isinstance(port, int) for port in ports):
            raise ValueError(f"Machine '{machine_name}' has invalid 'Ports' value")

        return ports

    def _parse_machines(self, machines_data: Mapping[str, Mapping[str, Any]]) -> MachinesMap:
        if not isinstance(machines_data, Mapping):
            raise ValueError("Invalid machine structure: expected a dictionary")

        machines_by_name: MachinesMap = {}
        for name, details in machines_data.items():
            if not isinstance(name, str) or not isinstance(details, Mapping):
                raise ValueError("Invalid machine structure: expected name/details mapping")
            self._validate_machine_details(name, details)
            machines_by_name[name] = dict(details)

        if not machines_by_name:
            raise ValueError("No machines found in machine data")

        return machines_by_name

    def _validate_machine_details(self, machine_name: str, details: Mapping[str, Any]) -> None:
        missing_fields = REQUIRED_MACHINE_FIELDS - set(details.keys())
        if missing_fields:
            missing = ", ".join(sorted(missing_fields))
            raise ValueError(f"Machine '{machine_name}' is missing fields: {missing}")

        ports = details.get("Ports")
        if not isinstance(ports, list) or not all(isinstance(port, int) for port in ports):
            raise ValueError(f"Machine '{machine_name}' has invalid 'Ports' value")

        if not isinstance(details.get("cores"), int):
            raise ValueError(f"Machine '{machine_name}' has invalid 'cores' value")

        if not isinstance(details.get("memory_gb"), int):
            raise ValueError(f"Machine '{machine_name}' has invalid 'memory_gb' value")

        if not isinstance(details.get(IN_USE_FIELD), bool):
            raise ValueError(f"Machine '{machine_name}' has invalid '{IN_USE_FIELD}' value")

    def _machines_dict(self) -> MachinesMap:
        return self._machines_by_name

    def _get_available_machines(self) -> MachinesMap:
        with self._lock:
            return {
                name: details
                for name, details in self._machines_dict().items()
                if details.get("memory_gb", 0) > 0 and not details.get(IN_USE_FIELD, False)
            }

    def _is_port_open(self, ip: str, port: int, timeout: float) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((ip, port)) == 0

    def _create_rpc_method(
        self,
        ip: str,
        ports: list[int],
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        if not ip:
            raise ValueError("IP is required")
        if not ports:
            raise ValueError("At least one port is required")

        for port in ports:
            if self._is_port_open(ip, port, timeout):
                return {"ip": ip, "port": port}

        raise ConnectionError(f"Could not connect to {ip} on any provided port")
