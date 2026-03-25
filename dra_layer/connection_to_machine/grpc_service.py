"""DRA gRPC server: implements `DRAService` from `dra.proto`."""

from __future__ import annotations

import logging
from concurrent import futures

import grpc
import psutil

from . import dra_pb2
from . import dra_pb2_grpc

logger = logging.getLogger(__name__)

_GB = 1024.0**3


def machine_info_from_psutil() -> dra_pb2.MachineInfoResponse:
    """Build `MachineInfoResponse` from this host (RAM + CPU via psutil)."""
    vm = psutil.virtual_memory()
    total_gb_used = vm.used / _GB
    available_gb = vm.available / _GB
    logical = int(psutil.cpu_count(logical=True) or 1)
    # Short sample so percent is meaningful (blocks ~100–200ms once per RPC).
    pct = float(psutil.cpu_percent(interval=0.15))
    avail_cores = max(0.0, float(logical) * (1.0 - min(100.0, pct) / 100.0))

    return dra_pb2.MachineInfoResponse(
        machine_state=dra_pb2.MachineState.ON,
        total_gb_used=round(total_gb_used, 3),
        available_gb_machine=round(available_gb, 3),
        total_cpu_cores=logical,
        available_cores_machine=round(avail_cores, 2),
        app_workloads=[],
    )


class DRAService(dra_pb2_grpc.DRAServiceServicer):
    def PowerOnMachine(self, request, context):
        return dra_pb2.PowerOnResponse(
            acceptance=True,
            machine_state=dra_pb2.MachineState.ON,
        )

    def PowerOffMachine(self, request, context):
        return dra_pb2.PowerOffResponse(
            acceptance=True,
            machine_state=dra_pb2.MachineState.OFF,
        )

    def DeployApp(self, request, context):
        return dra_pb2.DeployResponse(
            success=True,
            app_workload_id="stub",
            cpu_amt_used=0.0,
            gb_mem_amt_used=0.0,
            deploy_status="deployed",
        )

    def UndeployApp(self, request, context):
        snap = machine_info_from_psutil()
        return dra_pb2.UndeployResponse(
            success=True,
            freed_gb_app=0.0,
            cpu_used_app=0.0,
            available_gb_machine=snap.available_gb_machine,
            available_cores_machine=snap.available_cores_machine,
        )

    def GetMachineInfo(self, request, context):
        try:
            return machine_info_from_psutil()
        except Exception:
            logger.exception("GetMachineInfo: psutil failed")
            return dra_pb2.MachineInfoResponse(
                machine_state=dra_pb2.MachineState.ERROR,
                total_gb_used=0.0,
                available_gb_machine=0.0,
                total_cpu_cores=0,
                available_cores_machine=0.0,
                app_workloads=[],
            )


def serve(*, host: str = "0.0.0.0", port: int, max_workers: int = 4) -> None:
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=max_workers))
    dra_pb2_grpc.add_DRAServiceServicer_to_server(DRAService(), server)
    addr = f"{host}:{port}"
    server.add_insecure_port(addr)
    server.start()
    logger.info("DRA gRPC listening on %s", addr)
    server.wait_for_termination()
