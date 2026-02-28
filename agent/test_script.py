"""Quick test for _read_machines and Script."""
import os
import sys
import unittest

# Ensure agent dir is on path and we can import script
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestReadMachines(unittest.TestCase):
    def setUp(self):
        self.original_cwd = os.getcwd()
        os.chdir(os.path.dirname(os.path.abspath(__file__)))

    def tearDown(self):
        os.chdir(self.original_cwd)

    def test_read_machines_returns_data(self):
        """Test that machines are read from machines.json."""
        from script import Script
        s = Script()
        self.assertIsInstance(s.machines, list)
        self.assertGreater(len(s.machines), 0)

    def test_read_machines_structure(self):
        """Test that each nested machine has expected keys."""
        from script import Script
        s = Script()
        machines_dict = s.machines[0]  # Single-line JSON yields one dict in list
        expected_keys = {"IP", "Ports", "cores", "memory_gb", "In-use"}
        for machine in machines_dict.values():
            for key in expected_keys:
                self.assertIn(key, machine, f"Missing key: {key}")

    def test_machines_has_cores_and_memory(self):
        """Test that machines have cores and memory_gb values."""
        from script import Script
        s = Script()
        machines_dict = s.machines[0]
        for machine in machines_dict.values():
            self.assertIsInstance(machine.get("cores"), (int, type(None)))
            self.assertIsInstance(machine.get("memory_gb"), (int, type(None)))

    def test_print_available_machines(self):
        """Print machines that are available (memory_gb > 0)."""
        from script import Script
        s = Script()
        machines_dict = s.machines[0]
        available = [(name, info) for name, info in machines_dict.items()
                     if info.get("memory_gb", 0) > 0]
        print("\nAvailable machines (memory_gb > 0):")
        for name, info in available:
            print(f"  {name}: {info.get('cores')} cores, {info.get('memory_gb')} GB")


if __name__ == "__main__":
    unittest.main()
