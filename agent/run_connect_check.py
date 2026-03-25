"""One-shot check: Postgres machine list → first reachable gRPC target."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.env import get_metadata_dsn


def main() -> int:
    dsn = get_metadata_dsn()
    try:
        timeout = float(os.environ.get("CONNECT_TIMEOUT_SECONDS", "2.0"))
    except ValueError:
        print("Invalid CONNECT_TIMEOUT_SECONDS")
        return 2

    from agent.machine_metadata_manager import MachineMetadataManager
    from agent.rpc_client import DRAClient

    try:
        manager = MachineMetadataManager(dsn)
        name, client = DRAClient().connect_to_available_machine(manager, timeout=timeout)
    except Exception as exc:
        print(f"CONNECT_FAILED: {type(exc).__name__}: {exc}")
        return 1

    print(f"CONNECTED: {name} {client.ip}:{client.port}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
