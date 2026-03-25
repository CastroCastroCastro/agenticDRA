"""For each machine in metadata: connect → GetMachineInfo → close; print one line per row."""

from __future__ import annotations

import os
import sys
from pathlib import Path

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.env import get_metadata_dsn


def main() -> int:
    try:
        timeout = float(os.environ.get("CONNECT_TIMEOUT_SECONDS", "2.0"))
    except ValueError:
        print("Invalid CONNECT_TIMEOUT_SECONDS")
        return 2

    all_rows = "--all" in sys.argv

    from agent.machine_metadata_manager import MachineMetadataManager
    from agent.rpc_client import DRAClient

    dsn = get_metadata_dsn()
    manager = MachineMetadataManager(dsn)
    dra = DRAClient()

    for row in dra.each_machine_stats(manager, timeout=timeout, only_available=not all_rows):
        if row.error:
            print(f"{row.machine_name}\tERROR\t{row.error}")
        else:
            s = row.stats
            print(
                f"{row.machine_name}\tOK\t"
                f"state={s.machine_state} cores={s.total_cpu_cores} "
                f"avail_gb={s.available_gb_machine:.2f}"
            )
    return 0


if __name__ == "__main__":
    sys.exit(main())
