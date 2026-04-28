import asyncio
import logging
import os
import subprocess
import tempfile
from datetime import datetime, timezone

import httpx
import jwt

from db import get_settings, get_supabase
from services.app_logger import log_event

logger = logging.getLogger(__name__)

# Apenas estas vars de ambiente chegam ao subprocess — SERVICE_ROLE_KEY e
# ANTHROPIC_API_KEY são explicitamente excluídos para evitar acesso indevido.
_SAFE_ENV_KEYS = {"PATH", "HOME", "LANG", "TZ", "PYTHONPATH"}


def _get_service_token() -> str:
    s = get_settings()
    return jwt.encode(
        {"id": "agents-service", "role": "admin", "active": True},
        s.jwt_secret,
        algorithm="HS256",
    )


async def run_agent(agent: dict) -> dict:
    db = get_supabase()
    run = db.table("agent_runs").insert({
        "agent_id": agent["id"],
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).execute().data[0]
    run_id = run["id"]

    try:
        if agent["agent_type"] == "freshservice_sync":
            output = await _run_freshservice_sync()
        elif agent["agent_type"] == "script":
            output = await asyncio.get_event_loop().run_in_executor(
                None, _run_script_sync, agent
            )
        else:
            raise ValueError(f"Tipo desconhecido: {agent['agent_type']}")

        db.table("agent_runs").update({
            "status": "success",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "output": output,
        }).eq("id", run_id).execute()
        log_event("info", "agents", f"Agente '{agent['name']}' concluído")
        return {"status": "success", "run_id": run_id}

    except Exception as exc:
        db.table("agent_runs").update({
            "status": "error",
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "error": str(exc),
        }).eq("id", run_id).execute()
        log_event("error", "agents", f"Erro no agente '{agent['name']}'", detail=str(exc))
        return {"status": "error", "run_id": run_id, "error": str(exc)}


async def _run_freshservice_sync() -> str:
    freshservice_url = os.getenv("FRESHSERVICE_SERVICE_URL", "http://freshservice-service:8003")
    token = _get_service_token()
    async with httpx.AsyncClient(timeout=300.0) as client:
        r = await client.post(
            f"{freshservice_url}/api/freshservice/sync/daily",
            headers={"Authorization": f"Bearer {token}"},
        )
        r.raise_for_status()
    return "Sync Freshservice disparado via HTTP"


def _run_script_sync(agent: dict) -> str:
    code = (agent.get("config") or {}).get("code", "")
    if not code.strip():
        raise ValueError("Nenhum código definido no agente")

    safe_env = {k: v for k, v in os.environ.items() if k in _SAFE_ENV_KEYS}
    safe_env["SUPABASE_URL"] = os.environ.get("SUPABASE_URL", "")
    safe_env["SUPABASE_ANON_KEY"] = os.environ.get("SUPABASE_ANON_KEY", "")

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
        f.write(code)
        tmppath = f.name
    try:
        result = subprocess.run(
            ["python3", tmppath],
            capture_output=True, text=True, timeout=300,
            env=safe_env,
        )
        output = (result.stdout or "")[-10_000:]
        if result.returncode != 0:
            raise RuntimeError((result.stderr or "exit code não zero")[-2_000:])
        return output
    finally:
        os.unlink(tmppath)
