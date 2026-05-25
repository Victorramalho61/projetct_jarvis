import asyncio
import os
import signal
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from auth import require_role
from routes.config import read_config

router = APIRouter(prefix="/api/hermes")

# pid per platform — in-process registry (single container, single worker)
_gateway_pids: dict[str, int] = {}

SUPPORTED_PLATFORMS = ["telegram", "discord", "slack", "whatsapp", "signal", "email"]


@router.get("/gateways")
async def list_gateways(_: dict = Depends(require_role("admin"))):
    cfg = read_config()
    result: list[dict[str, Any]] = []
    for platform in SUPPORTED_PLATFORMS:
        pcfg = cfg.get("platforms", {}).get(platform, {})
        pid = _gateway_pids.get(platform)
        running = False
        if pid:
            try:
                os.kill(pid, 0)
                running = True
            except (ProcessLookupError, PermissionError):
                _gateway_pids.pop(platform, None)
        result.append({
            "platform": platform,
            "enabled": pcfg.get("enabled", False),
            "configured": bool(pcfg.get("token") or pcfg.get("address")),
            "running": running,
            "pid": pid if running else None,
        })
    return result


@router.post("/gateways/{platform}/start")
async def start_gateway(platform: str, _: dict = Depends(require_role("admin"))):
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(400, detail=f"Plataforma desconhecida: {platform}")

    if platform in _gateway_pids:
        pid = _gateway_pids[platform]
        try:
            os.kill(pid, 0)
            return {"status": "already_running", "pid": pid}
        except (ProcessLookupError, PermissionError):
            _gateway_pids.pop(platform, None)

    env = {**os.environ, "HERMES_GATEWAY_PLATFORM": platform}
    try:
        proc = await asyncio.create_subprocess_exec(
            "hermes", "gateway", "run",
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        _gateway_pids[platform] = proc.pid
        return {"status": "started", "pid": proc.pid}
    except FileNotFoundError:
        raise HTTPException(503, detail="hermes CLI não encontrado no container")


@router.post("/gateways/{platform}/stop")
async def stop_gateway(platform: str, _: dict = Depends(require_role("admin"))):
    if platform not in SUPPORTED_PLATFORMS:
        raise HTTPException(400, detail=f"Plataforma desconhecida: {platform}")

    pid = _gateway_pids.get(platform)
    if not pid:
        return {"status": "not_running"}

    try:
        os.kill(pid, signal.SIGTERM)
        _gateway_pids.pop(platform, None)
        return {"status": "stopped", "pid": pid}
    except (ProcessLookupError, PermissionError):
        _gateway_pids.pop(platform, None)
        return {"status": "not_found"}
