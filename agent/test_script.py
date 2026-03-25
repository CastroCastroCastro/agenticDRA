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

    def test_select_machines_sql_orders_by_memory_gb(self):
        from agent.machine_metadata_manager import SELECT_MACHINES_SQL

        lowered = SELECT_MACHINES_SQL.lower()
        self.assertIn("order by memory_gb desc", lowered)
        self.assertIn("machine_name", lowered)


class TestDRAClient(unittest.TestCase):
    def test_first_open_port_returns_first_listening(self):
        from agent.rpc_client import DRAClient

        dra = DRAClient()

        def fake_is_port_open(ip, port, timeout):
            return port == 5000

        dra._is_port_open = fake_is_port_open  # type: ignore[attr-defined]

        port = dra._first_open_port("127.0.0.1", [4102, 5000, 6000], timeout=0.01)
        self.assertEqual(port, 5000)

    def test_connect_to_machine_returns_client_for_first_open_port(self):
        from agent.rpc_client import DRAClient

        dra = DRAClient()

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
            dra._is_port_open = lambda ip, port, timeout: port == 6000  # type: ignore[attr-defined]

            client = dra.connect_to_machine("machine-a", [5000, 6000], timeout=0.01)
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
        from agent.rpc_client import DRAClient

        dra = DRAClient()

        import socket as _socket

        original_gethostbyname = _socket.gethostbyname
        _socket.gethostbyname = lambda _: "10.0.0.6"  # type: ignore[assignment]
        try:
            dra._is_port_open = lambda ip, port, timeout: False  # type: ignore[attr-defined]

            with self.assertRaisesRegex(ConnectionError, "Could not connect"):
                dra.connect_to_machine("machine-b", [5000, 6000], timeout=0.01)
        finally:
            _socket.gethostbyname = original_gethostbyname
    
    def test_connect_to_machine_from_metadata_uses_ip_and_ports(self):
        from agent.rpc_client import DRAClient

        dra = DRAClient()
        # Isolate this test to metadata parsing/forwarding only.
        dra.connect_to_ip = lambda ip, ports, timeout=1.0: (ip, ports, timeout)  # type: ignore[assignment]

        client = dra.connect_to_machine_from_metadata(
            "machine-a",
            {"IP": "10.0.0.10", "Ports": [5000, 6000], "In-use": False},
            timeout=0.25,
        )
        self.assertEqual(client, ("10.0.0.10", [5000, 6000], 0.25))
    
    def test_connect_to_available_machine_polls_and_skips_unreachable(self):
        from agent.rpc_client import DRAClient

        class StubMetadataManager:
            # Return two candidates so we can verify failover behavior.
            def get_available_machines(self, poll=True):
                return {
                    "bad-machine": {"IP": "10.0.0.11", "Ports": [5001], "In-use": False},
                    "good-machine": {"IP": "10.0.0.12", "Ports": [5002], "In-use": False},
                }

        dra = DRAClient()

        def fake_connect(machine_name, details, timeout=1.0):
            if machine_name == "bad-machine":
                raise ConnectionError("unreachable")
            return {"connected_to": machine_name}

        dra.connect_to_machine_from_metadata = fake_connect  # type: ignore[assignment]

        name, client = dra.connect_to_available_machine(StubMetadataManager(), timeout=0.5)
        self.assertEqual(name, "good-machine")
        self.assertEqual(client, {"connected_to": "good-machine"})

    def test_each_machine_stats_connects_calls_stats_closes(self):
        from unittest.mock import Mock

        from agent.rpc_client import DRAClient, MachineStatsRow

        class StubMetadataManager:
            def get_available_machines(self, poll=True):
                return {
                    "m1": {"IP": "10.0.0.1", "Ports": [1], "In-use": False},
                }

        dra = DRAClient()

        mock_client = Mock()
        mock_client.get_machine_stats = Mock(return_value="stats-payload")
        mock_client.close = Mock()
        dra.connect_to_machine_from_metadata = Mock(return_value=mock_client)  # type: ignore[method-assign]

        rows = list(dra.each_machine_stats(StubMetadataManager(), timeout=0.5))
        self.assertEqual(rows, [MachineStatsRow("m1", "stats-payload", None)])
        mock_client.get_machine_stats.assert_called_once_with(timeout=0.5)
        mock_client.close.assert_called_once_with()

    def test_each_machine_stats_closes_when_get_machine_stats_fails(self):
        from unittest.mock import Mock

        from agent.rpc_client import DRAClient

        class StubMetadataManager:
            def get_available_machines(self, poll=True):
                return {
                    "m1": {"IP": "10.0.0.1", "Ports": [1], "In-use": False},
                }

        dra = DRAClient()
        mock_client = Mock()
        mock_client.get_machine_stats = Mock(side_effect=RuntimeError("rpc failed"))
        mock_client.close = Mock()
        dra.connect_to_machine_from_metadata = Mock(return_value=mock_client)  # type: ignore[method-assign]

        rows = list(dra.each_machine_stats(StubMetadataManager(), timeout=0.5))
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0].stats)
        self.assertIn("RuntimeError", rows[0].error or "")
        mock_client.close.assert_called_once_with()

    def test_each_machine_stats_yields_error_when_connect_fails(self):
        from unittest.mock import Mock

        from agent.rpc_client import DRAClient

        class StubMetadataManager:
            def get_available_machines(self, poll=True):
                return {
                    "m1": {"IP": "10.0.0.1", "Ports": [1], "In-use": False},
                }

        dra = DRAClient()
        dra.connect_to_machine_from_metadata = Mock(side_effect=ConnectionError("down"))  # type: ignore[method-assign]

        rows = list(dra.each_machine_stats(StubMetadataManager(), timeout=0.5))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].machine_name, "m1")
        self.assertIsNone(rows[0].stats)
        self.assertIn("ConnectionError", rows[0].error or "")


class TestOpenAIMachineSelect(unittest.TestCase):
    def test_select_machine_name_openai_parses_json(self):
        from unittest.mock import Mock

        from agent.openai_machine_select import select_machine_name_openai

        machines = {
            "a": {"IP": "10.0.0.1", "Ports": [1], "cores": 4, "memory_gb": 8, "In-use": False},
            "b": {"IP": "10.0.0.2", "Ports": [2], "cores": 8, "memory_gb": 32, "In-use": False},
        }
        fake_resp = Mock()
        fake_resp.choices = [
            Mock(
                message=Mock(
                    content='{"machine_name": "b", "reason": "more RAM"}',
                )
            )
        ]
        oa = Mock()
        oa.chat.completions.create = Mock(return_value=fake_resp)

        name, reason = select_machine_name_openai(
            machines,
            user_instruction="pick highest memory",
            model="gpt-test",
            openai_client=oa,
        )
        self.assertEqual(name, "b")
        self.assertIn("RAM", reason)
        oa.chat.completions.create.assert_called_once()
        call_kw = oa.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kw["model"], "gpt-test")
        self.assertEqual(call_kw["response_format"], {"type": "json_object"})

    def test_select_machine_name_openai_rejects_unknown_name(self):
        from unittest.mock import Mock

        from agent.openai_machine_select import select_machine_name_openai

        machines = {"only": {"IP": "1.1.1.1", "Ports": [1], "cores": 1, "memory_gb": 1, "In-use": False}}
        fake_resp = Mock()
        fake_resp.choices = [Mock(message=Mock(content='{"machine_name": "ghost", "reason": "x"}'))]
        oa = Mock()
        oa.chat.completions.create = Mock(return_value=fake_resp)

        with self.assertRaisesRegex(ValueError, "not in candidates"):
            select_machine_name_openai(
                machines,
                openai_client=oa,
                model="gpt-test",
            )

    def test_connect_with_openai_selection_uses_chosen_machine(self):
        from unittest.mock import Mock

        from agent.openai_machine_select import connect_with_openai_selection
        from agent.rpc_client import DRAClient

        class Mgr:
            def get_available_machines(self, poll=True):
                return {
                    "m1": {"IP": "10.0.0.5", "Ports": [7000], "cores": 2, "memory_gb": 4, "In-use": False},
                }

        oa = Mock()
        oa.chat.completions.create = Mock(
            return_value=Mock(
                choices=[Mock(message=Mock(content='{"machine_name": "m1", "reason": "only option"}'))]
            )
        )
        dra = DRAClient()
        fake_mc = object()
        dra.connect_to_machine_from_metadata = Mock(return_value=fake_mc)  # type: ignore[method-assign]

        name, client, reason = connect_with_openai_selection(
            Mgr(),
            dra=dra,
            openai_client=oa,
            model="gpt-test",
            timeout=0.1,
        )
        self.assertEqual(name, "m1")
        self.assertIs(client, fake_mc)
        self.assertIn("only", reason)
        dra.connect_to_machine_from_metadata.assert_called_once()
        self.assertEqual(dra.connect_to_machine_from_metadata.call_args[0][0], "m1")

    def test_connect_with_openai_retries_after_connect_failure(self):
        from unittest.mock import Mock

        from agent.openai_machine_select import connect_with_openai_selection
        from agent.rpc_client import DRAClient

        class Mgr:
            def get_available_machines(self, poll=True):
                return {
                    "bad": {"IP": "10.0.0.1", "Ports": [1], "cores": 1, "memory_gb": 1, "In-use": False},
                    "good": {"IP": "10.0.0.2", "Ports": [2], "cores": 2, "memory_gb": 8, "In-use": False},
                }

        oa = Mock()
        r1 = Mock(
            choices=[Mock(message=Mock(content='{"machine_name": "bad", "reason": "first"}'))]
        )
        r2 = Mock(
            choices=[Mock(message=Mock(content='{"machine_name": "good", "reason": "second"}'))]
        )
        oa.chat.completions.create = Mock(side_effect=[r1, r2])

        dra = DRAClient()

        def connect_side_effect(name, details, timeout=1.0):
            if name == "bad":
                raise ConnectionError("unreachable")
            return f"client-{name}"

        dra.connect_to_machine_from_metadata = connect_side_effect  # type: ignore[method-assign]

        name, client, reason = connect_with_openai_selection(
            Mgr(),
            dra=dra,
            openai_client=oa,
            model="gpt-test",
            max_connect_retries=4,
        )
        self.assertEqual(name, "good")
        self.assertEqual(client, "client-good")
        self.assertEqual(oa.chat.completions.create.call_count, 2)
        self.assertIn("second", reason)
        self.assertIn("attempt 2", reason)


if __name__ == "__main__":
    unittest.main()
