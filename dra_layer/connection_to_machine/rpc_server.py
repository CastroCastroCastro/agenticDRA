from connection_to_machine.dra_pb2_grpc import DRAServiceServicer, add_DRAServiceServicer_to_server
from connection_to_machine.dra_pb2 import PowerOnRequest, PowerOnResponse, PowerOffRequest, PowerOffResponse, DeployRequest, DeployResponse, UndeployRequest, UndeployResponse, MachineInfoRequest, MachineInfoResponse

class DRAService(DRAServiceServicer):
    def PowerOnMachine(self, request, context):
        """
        Turns on machine when connected
        """
        return PowerOnResponse(acceptance=True, machine_state=MachineState.ON)

    def PowerOffMachine(self, request, context):
        """
        Turns off machine (e.g. on server interrupt)

        """

        return PowerOffResponse(acceptance=True, machine_state=MachineState.OFF)

    def DeployApp(self, request, context):
        """
        Deployment: consumes resources, gets GB from metadata store, unzips, calls psutil, updates DB state to ON
        """
        
        return DeployResponse(success=True, app_workload_id="123", cpu_amt_used=1.0, gb_mem_amt_used=1.0, deploy_status="deployed")

    def UndeployApp(self, request, context):
        """
        Undeployment: frees resources used during deployment (GB, cores, etc.)
        """

        return UndeployResponse(success=True, freed_gb_app=1.0, cpu_used_app=1.0, available_gb_machine=1.0, available_cores_machine=1.0)

    def GetMachineInfo(self, request, context):
        """
        Gets machine info (CPU cores, GB) via psutil from current machine
        """
        return MachineInfoResponse(machine_state=MachineState.ON, total_gb_used=1.0, available_gb_machine=1.0, total_cpu_cores=1, available_cores_machine=1, app_workloads=[RunningWorkload(app_workload_id="123", gb_used_workload=1.0, cpu_used_workload=1.0, status_app_workload=WorkloadState.RUNNING)])
