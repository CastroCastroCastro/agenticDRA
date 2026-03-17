from __future__ import annotations

import socket
from typing import Any

from agent.constants import DEFAULT_TIMEOUT_SECONDS

import grpc


class MachineClient:
    def __init__(self, ip, port, *, ready_timeout: float = DEFAULT_TIMEOUT_SECONDS):
        self.ip = ip
        self.port = port

        self.channel = grpc.insecure_channel(f"{ip}:{port}")

        # Fail fast if the target isn't reachable / not speaking gRPC.
        grpc.channel_ready_future(self.channel).result(timeout=ready_timeout)

        # Generated stubs may not exist yet in this repo.
        try:
            import service_pb2_grpc  # type: ignore
        except ModuleNotFoundError:
            self.stub = None
            return

        # TODO: change YourServiceStub to our actual generated stub name.
        self.stub = service_pb2_grpc.YourServiceStub(self.channel)
    
    
    def call_method(self, request):
        if self.stub is None:
            raise RuntimeError(
                "service_pb2_grpc is missing. Generate our actual gRPC stubs before calling methods"
            )
        raise NotImplementedError("TODO: implement RPC methods on our stub")
        



class RPCServer:
    def __init__(self):
        pass
                
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
            #  finding the first open port to connect to
            if self._is_port_open(ip, port, timeout):
                return {"ip": ip, "port": port}

        raise ConnectionError(f"Could not connect to {ip} on any provided port")
    
    
    def connect_to_machine(self, machine_name: str, ports: list[int], timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict[str, Any]:
        # Need try except block here because of network operations
        ip = socket.gethostbyname(machine_name)
        
        rpc_target = self._create_rpc_method(ip, ports, timeout)
        ip = rpc_target["ip"]
        port = rpc_target['port']
        
        return MachineClient(ip, port, ready_timeout=timeout)  # gRPC client for this machine
    
        
       