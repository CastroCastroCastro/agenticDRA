"""Tests for Script machine loading and filtering behavior."""

import os
import sys
import unittest

# Ensure agent directory is importable when run from project root.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class TestScript(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from script import Script

        cls.Script = Script
        cls.in_use_field = "In-use"

    def setUp(self):
        self.script = self.Script()

    def test_read_machines_returns_non_empty_list(self):
        self.assertIsInstance(self.script.machines, list)
        self.assertGreater(len(self.script.machines), 0)

    def test_read_machines_structure_has_expected_keys(self):
        machines_dict = self.script._machines_dict()
        expected_keys = {"IP", "Ports", "cores", "memory_gb", self.in_use_field}

        for machine in machines_dict.values():
            for key in expected_keys:
                self.assertIn(key, machine, f"Missing key: {key}")

    def test_machines_have_numeric_cores_and_memory(self):
        machines_dict = self.script._machines_dict()
        for machine in machines_dict.values():
            self.assertIsInstance(machine.get("cores"), int)
            self.assertIsInstance(machine.get("memory_gb"), int)

    def test_get_available_machines_filters_only_zero_memory(self):
        machine_names = list(self.script._machines_by_name)
        self.assertGreaterEqual(len(machine_names), 2)
        machine_one, machine_two = machine_names[:2]

        self.script._machines_by_name[machine_one]["memory_gb"] = 0
        self.script._machines_by_name[machine_two][self.in_use_field] = True

        available = self.script._get_available_machines()

        self.assertNotIn(machine_one, available)
        self.assertIn(machine_two, available)
        self.assertTrue(all(m.get("memory_gb", 0) > 0 for m in available.values()))

    def test_parse_machines_merges_all_entries(self):
        machines_data = [
            {
                "machine-a": {
                    "IP": "127.0.0.1",
                    "Ports": [4102],
                    "cores": 8,
                    "memory_gb": 32,
                    self.in_use_field: False,
                }
            },
            {
                "machine-b": {
                    "IP": "127.0.0.2",
                    "Ports": [4061],
                    "cores": 16,
                    "memory_gb": 0,
                    self.in_use_field: True,
                }
            },
        ]

        parsed = self.script._parse_machines(machines_data)
        print(f"Parsed machines with details: {parsed}")

        self.assertEqual(set(parsed), {"machine-a", "machine-b"})
        self.assertEqual(parsed["machine-a"]["memory_gb"], 32)
        self.assertEqual(parsed["machine-b"]["memory_gb"], 0)


if __name__ == "__main__":
    unittest.main()
