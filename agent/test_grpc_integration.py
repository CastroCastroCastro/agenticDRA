"""gRPC integration: local DRAService + `MachineClient.get_machine_stats` (no Postgres)."""

from __future__ import annotations

import socket
import unittest
from concurrent import futures

import grpc

from agent.rpc_client import MachineClient
from dra_layer.connection_to_machine import dra_pb2
from dra_layer.connection_to_machine import dra_pb2_grpc
from dra_layer.connection_to_machine.grpc_service import DRAService


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


class TestGrpcLoopback(unittest.TestCase):
    def test_get_machine_stats_against_local_server(self):
        port = _free_port()
        server = grpc.server(futures.ThreadPoolExecutor(max_workers=2))
        dra_pb2_grpc.add_DRAServiceServicer_to_server(DRAService(), server)
        server.add_insecure_port(f"127.0.0.1:{port}")
        server.start()
        try:
            client = MachineClient("127.0.0.1", port, ready_timeout=5.0)
            try:
                resp = client.get_machine_stats(timeout=5.0)
                self.assertIn(
                    resp.machine_state,
                    (dra_pb2.MachineState.ON, dra_pb2.MachineState.ERROR),
                )
                if resp.machine_state == dra_pb2.MachineState.ON:
                    self.assertGreaterEqual(resp.total_cpu_cores, 1)
                    self.assertGreater(resp.available_gb_machine, 0.0)
            finally:
                client.close()
        finally:
            server.stop(0)


if __name__ == "__main__":
    unittest.main()
