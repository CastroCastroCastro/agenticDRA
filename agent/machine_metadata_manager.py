from __future__ import annotations

import json
import threading
from collections.abc import Mapping
from typing import Any

from agent.constants import IN_USE_FIELD, REQUIRED_MACHINE_FIELDS
from agent.database.postgres import read_rows_from_postgres

MachineDetails = dict[str, Any]
MachinesMap = dict[str, MachineDetails]


SELECT_MACHINES_SQL = """
SELECT machine_name, IP, Ports, cores, memory_gb, in_use
FROM machines
ORDER BY machine_name
"""


class MachineMetadataManager:
    def __init__(self, dsn: str):
        self._lock = threading.Lock()
        self._dsn = dsn
        self.machines = self._read_machines()
        self._machines_by_name = self._parse_machines(self.machines)
        
    
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
    
    
    def _machines_dict(self) -> MachinesMap:
        return self._machines_by_name
    
    def _get_available_machines(self) -> MachinesMap:
        with self._lock:
            return {
                name: details
                for name, details in self._machines_dict().items()
                if details.get("memory_gb", 0) > 0 and not details.get(IN_USE_FIELD, False)
            }
            
    
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
    
    
    def _read_machines(self) -> MachinesMap:
        """Read machine metadata rows from PostgreSQL."""
        rows = self._read_rows_from_postgres(SELECT_MACHINES_SQL)
        return self._rows_to_machines(rows)

    def _read_rows_from_postgres(self, select_sql: str) -> list[tuple[Any, ...]]:
        return read_rows_from_postgres(self._dsn, select_sql)

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
