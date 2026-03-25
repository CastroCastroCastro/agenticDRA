"""Load local `.env` and resolve metadata DB URL (Postgres / Docker default)."""

from __future__ import annotations

import os
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]

# Host port must match docker-compose `ports:` (default 5433:5432 to avoid local Postgres on 5432).
DEFAULT_METADATA_DSN = "postgresql://postgres:postgres@localhost:5433/machines_db"

_dotenv_loaded = False


def load_app_env() -> None:
    """Load `<repo>/.env` once so `METADATA_DB_URL` is set without exporting in the shell."""
    global _dotenv_loaded
    if _dotenv_loaded:
        return
    _dotenv_loaded = True
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(_REPO_ROOT / ".env")


def get_metadata_dsn() -> str:
    """DSN for `MachineMetadataManager`; prefers `METADATA_DB_URL`, then `.env`, then Docker default."""
    load_app_env()
    return os.environ.get("METADATA_DB_URL", DEFAULT_METADATA_DSN)


def get_openai_api_key() -> str | None:
    """OpenAI API key from `OPENAI_API_KEY` (env or `.env`). Returns None if unset or blank."""
    load_app_env()
    key = os.environ.get("OPENAI_API_KEY")
    if key is None or not str(key).strip():
        return None
    return str(key).strip()


def require_openai_api_key() -> str:
    """Raises if `OPENAI_API_KEY` is missing (used by OpenAI machine-selection)."""
    key = get_openai_api_key()
    if not key:
        raise ValueError(
            "Set OPENAI_API_KEY in the environment or in a repo-root `.env` file "
            "(never commit the key to git)."
        )
    return key


def get_openai_model() -> str:
    """Chat model for machine selection (`OPENAI_MODEL`, default `gpt-4o-mini`)."""
    load_app_env()
    return os.environ.get("OPENAI_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
