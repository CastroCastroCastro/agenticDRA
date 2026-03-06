
# PostgreSQL in a container – step-by-step

This guide sets up a single PostgreSQL database in Docker for the project. All scripts use it via `METADATA_DB_URL` to keep machine state in one place.

---

## Prerequisites

- **Docker** and **Docker Compose** installed ([Get Docker](https://docs.docker.com/get-docker/)).
- **Python**: `pip install "psycopg[binary]"` (required when you run the script against Postgres).

---

## Step 1: Start PostgreSQL

From the **project root** (`agenticDRA/`):

```bash
docker compose up -d
```

- This starts a container named `agentic-postgres` with Postgres 16.
- Data is stored in a Docker volume `agentic-postgres-data` so it survives restarts.
- Postgres listens on **localhost:5432**.

Check that it’s running:

```bash
docker compose ps
```

You should see `agentic-postgres` with state `running`.

---

## Step 2: Set the database URL

Your script reads the URL from the **`METADATA_DB_URL`** environment variable.

**Option A – export in the shell (quick test):**

```bash
export METADATA_DB_URL="postgresql://postgres:postgres@localhost:5432/machines_db"
```

**Option B – use a `.env` file (recommended):**

1. Copy the example env file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` if you changed user/password/database in `docker-compose.yml`.
3. Load it before running the script (e.g. in the same terminal):
   ```bash
   set -a && source .env && set +a
   ```
   Or use a tool that loads `.env` automatically (e.g. `python-dotenv` in your app).

The URL must use the form:

`postgresql://USER:PASSWORD@HOST:PORT/DATABASE`

Default values from `docker-compose.yml`: user `postgres`, password `postgres`, database `machines_db`, host `localhost`, port `5432`.

---

## Step 3: Run your script

From the **`agent`** directory (so imports work):

```bash
cd agent
python -c "
from script import Script
s = Script()
print('Machines:', list(s.machines.keys()))
"
```

- The first time you connect, the code creates the **`machines`** table if it doesn’t exist (see `database/postgres.py`).
- If the table is empty, the script will raise: *"No machines found in metadata store"*. Add at least one row (Step 4) to use it normally.

---

## Step 4: (Optional) Add machine rows

To insert test data, connect with `psql`:

```bash
docker exec -it agentic-postgres psql -U postgres -d machines_db -c "
INSERT INTO machines (machine_name, IP, Ports, cores, memory_gb, in_use)
VALUES
  ('machine-a', '127.0.0.1', '[4102]', 8, 32, false),
  ('machine-b', '127.0.0.2', '[4061]', 16, 64, false)
ON CONFLICT (machine_name) DO NOTHING;
"
```

Or open an interactive session:

```bash
docker exec -it agentic-postgres psql -U postgres -d machines_db
```

Then run:

```sql
INSERT INTO machines (machine_name, IP, Ports, cores, memory_gb, in_use)
VALUES
  ('machine-a', '127.0.0.1', '[4102]', 8, 32, false),
  ('machine-b', '127.0.0.2', '[4061]', 16, 64, false);
```

---

## Step 5: Stop or remove the database

- **Stop the container (keep data):**
  ```bash
  docker compose down
  ```
- **Start again later:**
  ```bash
  docker compose up -d
  ```
- **Remove the container and delete all data:**
  ```bash
  docker compose down -v
  ```

---

## Summary

| Step | Action |
|------|--------|
| 1 | `docker compose up -d` from project root |
| 2 | Set `METADATA_DB_URL` (env var or `.env`) |
| 3 | Run your script from `agent/` (table is created on first connect) |
| 4 | (Optional) Insert rows into `machines` via `docker exec … psql` |
| 5 | Use `docker compose down` / `up -d` to stop/start; `down -v` to wipe data |

This gives you a single, global Postgres instance in a container that all your scripts can use to track machine state.

```

