# Local deployment — what actually runs (accurate)

This document matches the **current code**. The `.proto` file describes *intended* behavior; the Python server may still be a **stub**.

## What runs where

| Component | Where it runs | Role |
|-----------|----------------|------|
| **Postgres** | **Docker** (`docker-compose.yml`) | Stores the `machines` table (name, IP, `Ports` JSON, cores, memory, in_use). |
| **DRA gRPC server** | **Your machine** (`python agent/run_dra_server.py`) | Implements `DRAService` from `dra.proto` on a TCP port (default **7020**). |
| **Agent / checks** | **Your machine** (same venv) | Reads Postgres, opens gRPC clients to `IP:port` from metadata. |

There is **no Docker image for the DRA server or the agent** in this repo today. Only Postgres is containerized.

## End-to-end flow (local)

```mermaid
flowchart LR
  subgraph docker [Docker]
    PG[(Postgres :5433)]
  end
  subgraph host [Host Python]
    SEED[seed_dev_machine.py]
    SRV[run_dra_server.py]
    CLI[connect_check / stats / deploy demo]
    MM[MachineMetadataManager]
    GRPC[DRAClient / MachineClient]
  end
  SEED -->|INSERT/UPDATE machines| PG
  CLI --> MM
  MM -->|SELECT machines| PG
  CLI --> GRPC
  GRPC -->|TCP + gRPC| SRV
  SRV -->|GetMachineInfo=psutil; other RPCs partly stub| GRPC
```

1. **Start metadata DB:** `docker compose up -d` → Postgres on host port **5433**.
2. **Configure DSN:** `METADATA_DB_URL` (or `.env`) must point at that Postgres.
3. **Seed a row:** `python agent/seed_dev_machine.py` upserts e.g. `dev-local` with `IP=127.0.0.1` and `Ports=[7020]` (or `DRA_DEV_GRPC_PORT`).
4. **Start the DRA server:** `python agent/run_dra_server.py` binds **0.0.0.0:7020** (by default) so local clients can connect.
5. **Verify:**
   - `run_connect_check.py` — proves SQL → metadata → TCP probe → gRPC channel ready.
   - `run_machine_stats.py` — same, plus one `GetMachineInfo` RPC per machine, then channel closed.
   - `run_deploy_rpc_demo.py` — same connect path, then one **`DeployApp`** RPC (see below).

Automated bundle: `./scripts/live_e2e.sh` (seeds, starts server, runs checks, stops server).

## “Deployment” in this repo (be precise)

- **In `dra.proto`:** `DeployApp` takes `zip_file` bytes; comments mention unzip, psutil, DB updates, etc. That is **design intent**, not a guarantee about Python code.
- **In `dra_layer/connection_to_machine/grpc_service.py`:** `DeployApp` **does not** read the zip, write files, or update Postgres. It returns a **fixed stub** `DeployResponse` (`success=True`, `app_workload_id="stub"`, zero resource fields, `deploy_status="deployed"`).

So locally you can prove:

- The **gRPC deployment RPC is wired and callable** end-to-end.
- You **cannot** claim real app install, resource accounting, or DB state changes from deployment until that servicer is implemented.

`GetMachineInfo` uses **`psutil`** on the server host for RAM (used / available GB), logical CPU count, and a short **`cpu_percent`** sample to estimate `available_cores_machine`. `app_workloads` is still empty (no per-process tracking). On failure it returns `machine_state=ERROR`.

## Machine selection

`MachineMetadataManager` loads rows with:

`ORDER BY memory_gb DESC, machine_name ASC`

**Deterministic (no LLM):** `DRAClient.connect_to_available_machine` walks that ordered map and returns the **first** machine that passes TCP + gRPC ready (skips unreachable rows).

**OpenAI (prompt):** `agent/openai_machine_select.py` loads the same **available** machines, sends them as JSON in a chat prompt plus optional user hints, and requires the model to return `{"machine_name": "...", "reason": "..."}`. The code **rejects** names not in the candidate set, then connects **only** to the chosen row via `DRAClient.connect_to_machine_from_metadata`. If that host does not answer (TCP/gRPC), the failed name is **removed** from the next prompt and OpenAI is called again (up to **`OPENAI_MAX_CONNECT_RETRIES`**, default 4). CLI: `python agent/run_openai_connect.py` (needs `OPENAI_API_KEY` in env or `.env`; optional `OPENAI_MODEL`, default `gpt-4o-mini`).

## Insecure gRPC

The server uses **`add_insecure_port`**. There is no TLS in this path. Fine for localhost dev; **not** production-ready as-is.

## Quick commands (copy-paste)

```bash
docker compose up -d
export METADATA_DB_URL="postgresql://postgres:postgres@localhost:5433/machines_db"
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python agent/seed_dev_machine.py
# terminal A:
.venv/bin/python agent/run_dra_server.py
# terminal B:
.venv/bin/python agent/run_connect_check.py
.venv/bin/python agent/run_machine_stats.py
.venv/bin/python agent/run_deploy_rpc_demo.py
# optional — OpenAI picks the machine, then gRPC connect:
# .venv/bin/python agent/run_openai_connect.py "prefer highest memory_gb"
```

Or one shot: `./scripts/live_e2e.sh` (starts and stops the server for you). If **`OPENAI_API_KEY`** is set (e.g. in `.env`, loaded by the Python scripts), it also runs **`run_openai_connect.py`**; otherwise it prints a skip line.
