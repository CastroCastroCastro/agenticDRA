"""Connect to one machine after OpenAI picks `machine_name` from SQL candidates (needs OPENAI_API_KEY)."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.env import get_metadata_dsn
from agent.machine_metadata_manager import MachineMetadataManager
from agent.openai_machine_select import connect_with_openai_selection


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Load machines from Postgres, ask OpenAI which to use, open gRPC to that host only.",
    )
    p.add_argument(
        "instruction",
        nargs="*",
        default=[],
        help="Optional natural-language hints (e.g. prefer high memory)",
    )
    p.add_argument(
        "--model",
        default=None,
        help="Override OPENAI_MODEL for this run",
    )
    p.add_argument(
        "--max-retries",
        type=int,
        default=None,
        help="Max OpenAI+connect rounds (default: OPENAI_MAX_CONNECT_RETRIES or 4)",
    )
    return p


def main() -> int:
    args = _build_parser().parse_args()
    try:
        timeout = float(os.environ.get("CONNECT_TIMEOUT_SECONDS", "2.0"))
    except ValueError:
        print("Invalid CONNECT_TIMEOUT_SECONDS")
        return 2

    instruction = " ".join(args.instruction).strip()
    dsn = get_metadata_dsn()
    manager = MachineMetadataManager(dsn)

    max_retries = args.max_retries
    if max_retries is None:
        try:
            max_retries = int(os.environ.get("OPENAI_MAX_CONNECT_RETRIES", "4"))
        except ValueError:
            max_retries = 4

    try:
        name, client, reason = connect_with_openai_selection(
            manager,
            user_instruction=instruction,
            timeout=timeout,
            model=args.model,
            max_connect_retries=max_retries,
        )
    except Exception as exc:
        print(f"OPENAI_CONNECT_FAILED: {type(exc).__name__}: {exc}")
        return 1

    print(f"SELECTED: {name}")
    print(f"REASON: {reason}")
    print(f"CONNECTED: {name} {client.ip}:{client.port}")
    client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
