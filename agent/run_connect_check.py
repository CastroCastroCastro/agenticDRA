"""Quick SQL->machineMap->RPC connectivity check. FOR TESTING RPC CONNECTIONS SERVER ONLY"""

'''python3 agent/run_connect_check.py --loop # command to run continuously
'''

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

if __package__ is None or __package__ == "":
    # Allow running as `python3 agent/run_connect_check.py` from repo root.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.machine_metadata_manager import MachineMetadataManager
from agent.rpc_server import RPCServer


DEFAULT_DSN = "postgresql://postgres:postgres@localhost:5432/machines_db"


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SQL->machineMap->RPC connectivity check")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously instead of one-shot",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        help="Seconds between loop checks (default: 2.0)",
    )
    parser.add_argument(
        "--max-iterations",
        type=int,
        default=0,
        help="Stop after N iterations in loop mode (0 means infinite)",
    )
    return parser


def _check_once(dsn: str, timeout: float) -> tuple[bool, str]:
    try:
        # Recreate manager each run so loop mode always polls the latest SQL state.
        metadata_manager = MachineMetadataManager(dsn)
        rpc_server = RPCServer()
        machine_name, client = rpc_server.connect_to_available_machine(
            metadata_manager,
            timeout=timeout,
        )
    except Exception as exc:  # pragma: no cover - helper script error path
        return False, f"CONNECT_FAILED: {type(exc).__name__}: {exc}"

    return True, f"CONNECTED: {machine_name} {client.ip}:{client.port}"


def main() -> int:
    args = _build_parser().parse_args()
    dsn = os.environ.get("METADATA_DB_URL", DEFAULT_DSN)
    timeout_value = os.environ.get("CONNECT_TIMEOUT_SECONDS", "2.0")

    try:
        timeout = float(timeout_value)
    except ValueError:
        print(f"Invalid CONNECT_TIMEOUT_SECONDS value: {timeout_value}")
        return 2

    if not args.loop:
        ok, message = _check_once(dsn, timeout)
        print(message)
        return 0 if ok else 1

    iteration = 0
    while True:
        iteration += 1
        # Each iteration performs one full SQL->map->RPC connection attempt.
        ok, message = _check_once(dsn, timeout)
        print(f"[{iteration}] {message}", flush=True)
        if args.max_iterations > 0 and iteration >= args.max_iterations:
            return 0 if ok else 1
        time.sleep(max(args.interval, 0.1))

    return 0


if __name__ == "__main__":
    sys.exit(main())
