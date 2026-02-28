"""Utilities for selecting machines and preparing RPC connectivity."""

import json
import socket
import threading
from pathlib import Path
from collections.abc import Mapping, Sequence
from typing import Any


DEFAULT_TIMEOUT_SECONDS = 1.0

MachineDetails = dict[str, Any]
MachinesMap = dict[str, MachineDetails]


class Script:
    def __init__(self, machines_path: str = "machines.json"):
        """Load machine definitions and prepare synchronization primitives."""
        self._lock = threading.Lock()
        self.machines = self._read_machines(machines_path)
        self._machines_by_name = self._parse_machines(self.machines)

    def _read_machines(self, machines_path: str) -> list[dict[str, Any]]:
        """Read machine configuration from JSON and return raw data as a list."""
        path = Path(machines_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parent / path

        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, dict) and data:
            return [data]
        if isinstance(data, list) and data:
            return data
        raise ValueError("No machines found in the file")

    def _parse_machines(self, machines_data: Sequence[Mapping[str, Any]]) -> MachinesMap:
        """Normalize loaded machine data into a machine-name keyed dictionary."""
        machines_by_name: MachinesMap = {}

        for entry in machines_data:
            if not isinstance(entry, Mapping):
                raise ValueError("Invalid machine structure: expected a dictionary")

            for name, details in entry.items():
                if not isinstance(name, str) or not isinstance(details, Mapping):
                    raise ValueError("Invalid machine structure: expected name/details mapping")
                machines_by_name[name] = dict(details)

        if not machines_by_name:
            raise ValueError("No machines found in machine data")

        return machines_by_name

    def _machines_dict(self) -> MachinesMap:
        """Return the machine-name keyed dictionary."""
        return self._machines_by_name

    def _get_available_machines(self) -> MachinesMap:
        """Return machines that have memory and are currently not filled."""
        with self._lock:
            return {
                name: details
                for name, details in self._machines_dict().items()
                if details.get("memory_gb", 0) > 0 
            }

    def _is_port_open(self, ip: str, port: int, timeout: float) -> bool:
        """Return True when a TCP connection can be established for ip/port."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((ip, port)) == 0

    def _create_rpc_method(
        self,
        ip: str,
        ports: list[int],
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """Return RPC endpoint details using the first reachable port."""
        if not ip:
            raise ValueError("IP is required")
        if not ports:
            raise ValueError("At least one port is required")

        for port in ports:
            if self._is_port_open(ip, port, timeout):
                return {"ip": ip, "port": port}

        raise ConnectionError(f"Could not connect to {ip} on any provided port")
