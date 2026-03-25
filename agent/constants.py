"""Shared constants for the agent package."""

DEFAULT_TIMEOUT_SECONDS = 1.0

# Default gRPC port for `agent/run_dra_server.py` and `agent/seed_dev_machine.py` (avoids macOS 5000/7000 listeners).
DEFAULT_DRA_GRPC_PORT = 7020

IN_USE_FIELD = "In-use"
REQUIRED_MACHINE_FIELDS = {"IP", "Ports", "cores", "memory_gb", IN_USE_FIELD}

