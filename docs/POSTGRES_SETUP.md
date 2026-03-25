# Postgres for machine metadata

Machines live in table `machines` (created on first connect). Scripts use **`METADATA_DB_URL`**.

## Start DB

From the repo root:

```bash
docker compose up -d
```

Postgres is on **localhost:5433** (avoids clashing with a local Postgres on 5432).

## Configure

```bash
cp .env.example .env
# ensure METADATA_DB_URL uses port 5433, e.g. postgresql://postgres:postgres@localhost:5433/machines_db
```

## Use with the agent

```bash
python3 agent/seed_dev_machine.py
python3 agent/run_dra_server.py   # other terminal
python3 agent/run_connect_check.py
```

If connect fails, the row’s **`Ports`** must match a running `run_dra_server.py` (default **7020**).

## Stop

```bash
docker compose down      # keep data
docker compose down -v     # delete volume
```
