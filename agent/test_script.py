"""Tests for machine metadata and RPC helper behavior."""

import unittest


class TestMachineMetadataManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from agent.machine_metadata_manager import MachineMetadataManager

        class StubbedManager(MachineMetadataManager):
            def __init__(self):
                # Skip reading from Postgres; we'll stub rows.
                import threading

                self._lock = threading.Lock()
                self._dsn = "postgresql://stub"
                self.machines = self._rows_to_machines(self._read_rows_from_postgres("SELECT 1"))
                self._machines_by_name = self._parse_machines(self.machines)

            def _read_rows_from_postgres(self, select_sql):
                return [
                    ("machine-a", "127.0.0.1", [4102], 8, 32, False),
                    ("machine-b", "127.0.0.2", [4061], 16, 153, False),
                    ("machine-c", "127.0.0.3", [5000], 4, 16, False),
                ]

        cls.Manager = StubbedManager

    def setUp(self):
        self.manager = self.Manager()

    def test_read_machines_returns_non_empty_map(self):
        self.assertIsInstance(self.manager.machines, dict)
        self.assertGreater(len(self.manager.machines), 0)

    def test_machine_structure_has_expected_keys(self):
        machines_dict = self.manager._machines_dict()
        expected_keys = {"IP", "Ports", "cores", "memory_gb", "In-use"}
        for machine in machines_dict.values():
            for key in expected_keys:
                self.assertIn(key, machine, f"Missing key: {key}")

    def test_get_available_machines_excludes_in_use_and_zero_memory(self):
        # Make two machines unavailable
        machine_names = list(self.manager._machines_by_name)
        machine_one, machine_two = machine_names[:2]
        self.manager._machines_by_name[machine_one]["memory_gb"] = 0
        self.manager._machines_by_name[machine_two]["In-use"] = True

        available = self.manager._get_available_machines()
        self.assertNotIn(machine_one, available)
        self.assertNotIn(machine_two, available)

    def test_parse_ports_accepts_json_string(self):
        ports = self.manager._parse_ports("machine-x", "[1, 2, 3]")
        self.assertEqual(ports, [1, 2, 3])

    def test_parse_ports_rejects_non_int_list(self):
        with self.assertRaisesRegex(ValueError, "invalid 'Ports' value"):
            self.manager._parse_ports("machine-x", ["5432"])
    
    def test_get_available_machines_can_poll(self):
        # Verifies get_available_machines(poll=True) triggers a fresh SQL read.
        class PollingManager(self.Manager):
            def __init__(self):
                self.read_calls = 0
                super().__init__()
            
            def _read_rows_from_postgres(self, select_sql):
                self.read_calls += 1
                return [
                    ("machine-z", "127.0.0.9", [7000], 8, 32, False),
                ]
        
        manager = PollingManager()
        available = manager.get_available_machines(poll=True)
        self.assertEqual(manager.read_calls, 2)
        self.assertEqual(list(available.keys()), ["machine-z"])

    def test_validate_machine_details_missing_field_raises(self):
        with self.assertRaisesRegex(ValueError, "missing fields"):
            self.manager._validate_machine_details(
                "machine-x",
                {
                    "IP": "127.0.0.1",
                    # Ports missing
                    "cores": 4,
                    "memory_gb": 16,
                    "In-use": False,
                },
            )


class TestRPCServer(unittest.TestCase):
    def test_create_rpc_method_returns_first_open_port(self):
        from agent.rpc_server import RPCServer

        server = RPCServer()

        def fake_is_port_open(ip, port, timeout):
            return port == 5000

        server._is_port_open = fake_is_port_open  # type: ignore[attr-defined]

        target = server._create_rpc_method("127.0.0.1", [4102, 5000, 6000], timeout=0.01)
        self.assertEqual(target, {"ip": "127.0.0.1", "port": 5000})

    def test_connect_to_machine_returns_client_for_first_open_port(self):
        from agent.rpc_server import RPCServer

        server = RPCServer()

        # Mock channel creation so tests don't create real gRPC channel objects.
        import grpc as _grpc
        from unittest.mock import Mock

        original_insecure_channel = _grpc.insecure_channel
        original_channel_ready_future = _grpc.channel_ready_future

        channel_obj = object()
        insecure_channel_mock = Mock(name="insecure_channel", return_value=channel_obj)
        _grpc.insecure_channel = insecure_channel_mock  # type: ignore[assignment]

        ready_future = Mock(name="ready_future")
        ready_future.result = Mock(name="ready_result", return_value=None)
        channel_ready_future_mock = Mock(name="channel_ready_future", return_value=ready_future)
        _grpc.channel_ready_future = channel_ready_future_mock  # type: ignore[assignment]

        # Stub DNS resolution
        import socket as _socket

        original_gethostbyname = _socket.gethostbyname
        _socket.gethostbyname = lambda _: "10.0.0.5"  # type: ignore[assignment]
        try:
            # Stub port probing: only 6000 is open
            server._is_port_open = lambda ip, port, timeout: port == 6000  # type: ignore[attr-defined]

            client = server.connect_to_machine("machine-a", [5000, 6000], timeout=0.01)
            self.assertEqual(client.ip, "10.0.0.5")
            self.assertEqual(client.port, 6000)
            insecure_channel_mock.assert_called_once_with("10.0.0.5:6000")
            channel_ready_future_mock.assert_called_once_with(channel_obj)
            ready_future.result.assert_called_once_with(timeout=0.01)
        finally:
            _socket.gethostbyname = original_gethostbyname
            _grpc.insecure_channel = original_insecure_channel
            _grpc.channel_ready_future = original_channel_ready_future

    def test_connect_to_machine_raises_when_no_ports_open(self):
        from agent.rpc_server import RPCServer

        server = RPCServer()

        import socket as _socket

        original_gethostbyname = _socket.gethostbyname
        _socket.gethostbyname = lambda _: "10.0.0.6"  # type: ignore[assignment]
        try:
            server._is_port_open = lambda ip, port, timeout: False  # type: ignore[attr-defined]

            with self.assertRaisesRegex(ConnectionError, "Could not connect"):
                server.connect_to_machine("machine-b", [5000, 6000], timeout=0.01)
        finally:
            _socket.gethostbyname = original_gethostbyname
    
    def test_connect_to_machine_from_metadata_uses_ip_and_ports(self):
        from agent.rpc_server import RPCServer
        
        server = RPCServer()
        # Isolate this test to metadata parsing/forwarding only.
        server.connect_to_ip = lambda ip, ports, timeout=1.0: (ip, ports, timeout)  # type: ignore[assignment]
        
        client = server.connect_to_machine_from_metadata(
            "machine-a",
            {"IP": "10.0.0.10", "Ports": [5000, 6000], "In-use": False},
            timeout=0.25,
        )
        self.assertEqual(client, ("10.0.0.10", [5000, 6000], 0.25))
    
    def test_connect_to_available_machine_polls_and_skips_unreachable(self):
        from agent.rpc_server import RPCServer
        
        class StubMetadataManager:
            # Return two candidates so we can verify failover behavior.
            def get_available_machines(self, poll=True):
                return {
                    "bad-machine": {"IP": "10.0.0.11", "Ports": [5001], "In-use": False},
                    "good-machine": {"IP": "10.0.0.12", "Ports": [5002], "In-use": False},
                }
        
        server = RPCServer()
        
        def fake_connect(machine_name, details, timeout=1.0):
            if machine_name == "bad-machine":
                raise ConnectionError("unreachable")
            return {"connected_to": machine_name}
        
        server.connect_to_machine_from_metadata = fake_connect  # type: ignore[assignment]
        
        name, client = server.connect_to_available_machine(StubMetadataManager(), timeout=0.5)
        self.assertEqual(name, "good-machine")
        self.assertEqual(client, {"connected_to": "good-machine"})


if __name__ == "__main__":
    unittest.main()
