from __future__ import annotations

import socket
import sys
from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, NamedTuple

import grpc

from agent.constants import DEFAULT_TIMEOUT_SECONDS, IN_USE_FIELD


class MachineStatsRow(NamedTuple):
    """Result of one connect → GetMachineInfo → close cycle."""

    machine_name: str
    stats: Any | None  # `dra_pb2.MachineInfoResponse` on success
    error: str | None


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


class MachineClient:
    """gRPC channel + `DRAServiceStub` for one host:port."""

    def __init__(self, ip: str, port: int, *, ready_timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.ip = ip
        self.port = port
        self.channel = grpc.insecure_channel(f"{ip}:{port}")
        grpc.channel_ready_future(self.channel).result(timeout=ready_timeout)

        self.stub = None
        root = str(_repo_root())
        if root not in sys.path:
            sys.path.insert(0, root)
        try:
            from dra_layer.connection_to_machine import dra_pb2_grpc

            self.stub = dra_pb2_grpc.DRAServiceStub(self.channel)
        except (ImportError, AttributeError, TypeError):
            self.stub = None

    def close(self) -> None:
        self.channel.close()

    def get_machine_stats(self, *, timeout: float | None = None) -> Any:
        """Calls `DRAService.GetMachineInfo` (proto); named *stats* in the API you described."""
        if self.stub is None:
            raise RuntimeError("DRA gRPC stub unavailable; check dra_layer is on PYTHONPATH")
        from dra_layer.connection_to_machine import dra_pb2

        t = DEFAULT_TIMEOUT_SECONDS if timeout is None else timeout
        return self.stub.GetMachineInfo(dra_pb2.Empty(), timeout=t)


class DRAClient:
    """Pick a machine from SQL metadata and open a `MachineClient` (TCP probe + gRPC ready)."""

    def _is_port_open(self, ip: str, port: int, timeout: float) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(timeout)
            return sock.connect_ex((ip, port)) == 0

    def _first_open_port(self, ip: str, ports: list[int], timeout: float) -> int:
        if not ip:
            raise ValueError("IP is required")
        if not ports:
            raise ValueError("At least one port is required")
        for port in ports:
            if self._is_port_open(ip, port, timeout):
                return port
        raise ConnectionError(f"Could not connect to {ip} on any provided port")

    def connect_to_machine(
        self, machine_name: str, ports: list[int], timeout: float = DEFAULT_TIMEOUT_SECONDS
    ) -> MachineClient:
        ip = socket.gethostbyname(machine_name)
        port = self._first_open_port(ip, ports, timeout)
        return MachineClient(ip, port, ready_timeout=timeout)

    def connect_to_machine_from_metadata(
        self,
        machine_name: str,
        machine_details: Mapping[str, Any],
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        *,
        ignore_in_use: bool = False,
    ) -> MachineClient:
        ip = machine_details.get("IP")
        ports = machine_details.get("Ports")
        if not isinstance(ip, str) or not ip:
            raise ValueError(f"Machine '{machine_name}' has invalid IP in metadata")
        if not isinstance(ports, list) or not all(isinstance(p, int) for p in ports):
            raise ValueError(f"Machine '{machine_name}' has invalid Ports in metadata")
        if machine_details.get(IN_USE_FIELD, False) and not ignore_in_use:
            raise ValueError(f"Machine '{machine_name}' is marked as in use")
        return self.connect_to_ip(ip, ports, timeout=timeout)

    def connect_to_ip(
        self, ip: str, ports: list[int], timeout: float = DEFAULT_TIMEOUT_SECONDS
    ) -> MachineClient:
        port = self._first_open_port(ip, ports, timeout)
        return MachineClient(ip, port, ready_timeout=timeout)

    def connect_to_available_machine(
        self,
        metadata_manager,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
    ) -> tuple[str, MachineClient]:
        available = metadata_manager.get_available_machines(poll=True)
        if not available:
            raise ConnectionError(
                "No available machines (empty, all in_use, or all memory_gb=0)"
            )
        for machine_name, details in available.items():
            try:
                return machine_name, self.connect_to_machine_from_metadata(
                    machine_name, details, timeout=timeout
                )
            except Exception:
                continue
        raise ConnectionError("Could not connect to any available machine")

    def each_machine_stats(
        self,
        metadata_manager,
        *,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        only_available: bool = True,
    ) -> Iterator[MachineStatsRow]:
        """For each machine: connect, `GetMachineInfo`, close. Order matches SQL (`memory_gb` desc)."""
        if only_available:
            machines = metadata_manager.get_available_machines(poll=True)
        else:
            machines = metadata_manager.poll_machines()

        for name, details in machines.items():
            client: MachineClient | None = None
            try:
                client = self.connect_to_machine_from_metadata(
                    name,
                    details,
                    timeout=timeout,
                    ignore_in_use=not only_available,
                )
                stats = client.get_machine_stats(timeout=timeout)
                yield MachineStatsRow(name, stats, None)
            except Exception as exc:
                yield MachineStatsRow(name, None, f"{type(exc).__name__}: {exc}")
            finally:
                if client is not None:
                    client.close()
