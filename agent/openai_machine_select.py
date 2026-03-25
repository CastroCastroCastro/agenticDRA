"""Use OpenAI to pick a `machine_name` from Postgres-backed candidates, then connect with `DRAClient`."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from agent.constants import DEFAULT_TIMEOUT_SECONDS
from agent.env import get_openai_model, require_openai_api_key
from agent.rpc_client import DRAClient, MachineClient

_SYSTEM = """You must choose exactly one machine from the candidate list.
Reply with a single JSON object only, using this shape:
{"machine_name": "<exact name from list>", "reason": "<one short sentence>"}
The machine_name value must match one of the candidate machine_name strings exactly (case-sensitive).
If the user says some machines failed to connect, you must pick a different machine_name from the list."""


def _candidates_json(machines: Mapping[str, Mapping[str, Any]]) -> str:
    rows: list[dict[str, Any]] = []
    for name, d in machines.items():
        rows.append(
            {
                "machine_name": name,
                "IP": d.get("IP"),
                "Ports": d.get("Ports"),
                "cores": d.get("cores"),
                "memory_gb": d.get("memory_gb"),
                "In-use": d.get("In-use"),
            }
        )
    return json.dumps(rows, indent=2)


def select_machine_name_openai(
    available_machines: Mapping[str, Mapping[str, Any]],
    *,
    user_instruction: str = "",
    extra_context: str = "",
    model: str | None = None,
    openai_client: Any | None = None,
) -> tuple[str, str]:
    """Call OpenAI; return `(machine_name, reason)` validated against `available_machines`."""
    if not available_machines:
        raise ValueError("No machines to choose from")
    valid = list(available_machines.keys())

    user_block = (
        "Candidate machines:\n"
        + _candidates_json(available_machines)
        + "\n\nUser priority / context:\n"
        + (
            user_instruction.strip()
            or "Choose the best machine for a typical workload. Prefer higher memory_gb when unsure."
        )
    )
    if extra_context.strip():
        user_block += "\n\n" + extra_context.strip()

    use_model = (model or get_openai_model()).strip() or "gpt-4o-mini"

    if openai_client is None:
        from openai import OpenAI

        client = OpenAI(api_key=require_openai_api_key())
    else:
        client = openai_client

    resp = client.chat.completions.create(
        model=use_model,
        messages=[
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": user_block},
        ],
        response_format={"type": "json_object"},
        temperature=0.2,
    )
    raw = resp.choices[0].message.content
    if not raw:
        raise RuntimeError("OpenAI returned empty message content")

    data = json.loads(raw)
    name = data.get("machine_name")
    reason = data.get("reason", "")
    if not isinstance(name, str):
        raise ValueError(f"OpenAI JSON missing string machine_name: {data!r}")
    if name not in available_machines:
        raise ValueError(
            f"OpenAI chose {name!r} which is not in candidates {valid}. "
            "Try a clearer instruction or fix metadata."
        )
    return name, str(reason)


def _failures_context(failures: list[tuple[str, str]]) -> str:
    if not failures:
        return ""
    lines = [
        "These machine_name values were already tried but gRPC/TCP connection failed — choose a different name from the candidate list only:"
    ]
    for n, err in failures:
        lines.append(f"- {n}: {err}")
    return "\n".join(lines)


def connect_with_openai_selection(
    metadata_manager: Any,
    *,
    dra: DRAClient | None = None,
    user_instruction: str = "",
    timeout: float = DEFAULT_TIMEOUT_SECONDS,
    model: str | None = None,
    openai_client: Any | None = None,
    max_connect_retries: int = 4,
) -> tuple[str, MachineClient, str]:
    """Poll SQL → prompt OpenAI → connect. Retries with a smaller candidate set if connect fails."""
    all_available = metadata_manager.get_available_machines(poll=True)
    if not all_available:
        raise ConnectionError(
            "No available machines (empty, all in_use, or all memory_gb=0)"
        )

    candidates: dict[str, Any] = dict(all_available)
    failures: list[tuple[str, str]] = []
    dra_client = dra or DRAClient()
    last_error: BaseException | None = None

    for attempt in range(max(1, max_connect_retries)):
        if not candidates:
            break
        name, reason = select_machine_name_openai(
            candidates,
            user_instruction=user_instruction,
            extra_context=_failures_context(failures),
            model=model,
            openai_client=openai_client,
        )
        try:
            details = all_available[name]
            grpc_client = dra_client.connect_to_machine_from_metadata(
                name, details, timeout=timeout
            )
            suffix = f" [openai attempt {attempt + 1}]" if attempt else ""
            return name, grpc_client, reason + suffix
        except BaseException as exc:
            last_error = exc
            failures.append((name, f"{type(exc).__name__}: {exc}"))
            if name in candidates:
                del candidates[name]

    msg = "Could not connect to any machine chosen by OpenAI"
    if failures:
        msg += ": " + "; ".join(f"{n} ({e})" for n, e in failures)
    raise ConnectionError(msg) from last_error
