"""After DB-driven connect: call DeployApp once over gRPC (server is stub; proves RPC path)."""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.env import get_metadata_dsn
from agent.machine_metadata_manager import MachineMetadataManager
from agent.rpc_client import DRAClient
from dra_layer.connection_to_machine import dra_pb2


def main() -> int:
    dsn = get_metadata_dsn()
    manager = MachineMetadataManager(dsn)
    dra = DRAClient()
    name, client = dra.connect_to_available_machine(manager)
    if client.stub is None:
        print("DEPLOY_DEMO_FAILED: gRPC stub missing")
        return 1
    endpoint = f"{client.ip}:{client.port}"
    try:
        req = dra_pb2.DeployRequest(zip_file=b"")
        resp = client.stub.DeployApp(req, timeout=10.0)
    finally:
        client.close()

    print(
        f"DEPLOY_RPC_OK: machine={name} endpoint={endpoint} "
        f"success={resp.success} app_workload_id={resp.app_workload_id!r} "
        f"status={resp.deploy_status!r} "
        f"(server stub — does not install zip; see docs/LOCAL_DEPLOYMENT.md)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
