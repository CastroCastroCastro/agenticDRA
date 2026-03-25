# agenticDRA

[![CI Pipeline Badge](https://github.com/CastroCastroCastro/agenticDRA/actions/workflows/ci-cd.yml/badge.svg)](https://github.com/CastroCastroCastro/agenticDRA/actions/workflows/ci-cd.yml)

## Local dev (Postgres + gRPC)

1. `docker compose up -d` — Postgres on **localhost:5433** (see `METADATA_DB_URL` in `.env.example`).
2. `python3 agent/seed_dev_machine.py` — seeds `dev-local` → `127.0.0.1:7020`.
3. `python3 agent/run_dra_server.py` — gRPC on **7020** (override with `DRA_DEV_GRPC_PORT`).
4. `python3 agent/run_connect_check.py` — should print `CONNECTED: dev-local …`.
5. Optional: `python3 agent/run_machine_stats.py` — per machine: connect → `GetMachineInfo` → close (`--all` includes in-use rows).
6. Optional: `python3 agent/run_deploy_rpc_demo.py` — connect → **`DeployApp`** RPC once (server returns a **stub**; see below).

**OpenAI machine choice:** set `OPENAI_API_KEY`, run `python agent/run_openai_connect.py` (optional hints as args). See `docs/LOCAL_DEPLOYMENT.md`.

**What “works” locally vs stub:** `docs/LOCAL_DEPLOYMENT.md` (process diagram, Postgres vs host, honest `DeployApp` / `GetMachineInfo` behavior).

Postgres only: `docs/POSTGRES_SETUP.md`.

## Tests

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
PYTHONPATH=. .venv/bin/python -m unittest discover -s agent -v
```

Includes a real gRPC loopback test (`test_grpc_integration.py`).

**Live E2E** (Postgres container + real gRPC server): after `docker compose up -d`,

```bash
./scripts/live_e2e.sh
```

Uses `METADATA_DB_URL` if set; otherwise defaults to `localhost:5433`. Stale `machines` rows with dead ports show as `ERROR` in `run_machine_stats` until you fix or delete them.
