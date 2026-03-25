"""Run the DRA gRPC server (use with Postgres row pointing at this host:port)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.constants import DEFAULT_DRA_GRPC_PORT


def main() -> None:
    parser = argparse.ArgumentParser(description="Start DRA gRPC server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_DRA_GRPC_PORT,
        help=f"gRPC port (default {DEFAULT_DRA_GRPC_PORT})",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    from dra_layer.connection_to_machine.grpc_service import serve

    serve(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
