"""
Rotas de versionamento de agentes.
- GET    /api/agents/versions/{name}          — lista todas as versões
- POST   /api/agents/versions/{name}          — registra nova versão (draft)
- PATCH  /api/agents/versions/{name}/{ver}/test     — marca como testing
- PATCH  /api/agents/versions/{name}/{ver}/approve  — aprova
- PATCH  /api/agents/versions/{name}/{ver}/canary   — inicia canary
- PATCH  /api/agents/versions/{name}/{ver}/promote  — promove canary → approved
- POST   /api/agents/versions/{name}/rollback       — rollback para versão anterior
"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_role

logger = logging.getLogger(__name__)
router = APIRouter(tags=["versioning"])


# ── Models ────────────────────────────────────────────────────────────────────

class RegisterVersionIn(BaseModel):
    version: str
    system_prompt: str
    tools: list[str] = []
    model: str = "llama3.2:1b"
    config: dict = {}
    notes: str = ""
    parent_version: Optional[str] = None
    created_by: str = "admin"


class ApproveIn(BaseModel):
    approved_by: str = "admin"


class CanaryIn(BaseModel):
    percentage: int = 10


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/agents/versions/{agent_name}")
async def list_versions(
    agent_name: str,
    _user: dict = Depends(require_role("admin")),
):
    from graph_engine.agent_versioning import get_registry
    try:
        versions = get_registry().list_versions(agent_name)
        return {"agent_name": agent_name, "versions": versions}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/agents/versions/{agent_name}")
async def register_version(
    agent_name: str,
    body: RegisterVersionIn,
    _user: dict = Depends(require_role("admin")),
):
    from graph_engine.agent_versioning import get_registry, AgentRegistry
    registry = get_registry()
    errors = AgentRegistry.validate_prompt(body.system_prompt)
    if errors:
        raise HTTPException(status_code=422, detail={"prompt_errors": errors})
    try:
        version = registry.register(
            agent_name=agent_name,
            version=body.version,
            system_prompt=body.system_prompt,
            tools=body.tools,
            model=body.model,
            config=body.config,
            created_by=body.created_by,
            notes=body.notes,
            parent_version=body.parent_version,
        )
        return {"ok": True, "version": version}
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/versions/{agent_name}/{version}/test")
async def mark_testing(
    agent_name: str,
    version: str,
    _user: dict = Depends(require_role("admin")),
):
    from graph_engine.agent_versioning import get_registry
    try:
        row = get_registry().mark_testing(agent_name, version)
        return {"ok": True, "version": row}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/versions/{agent_name}/{version}/approve")
async def approve_version(
    agent_name: str,
    version: str,
    body: ApproveIn = ApproveIn(),
    _user: dict = Depends(require_role("admin")),
):
    from graph_engine.agent_versioning import get_registry
    try:
        row = get_registry().mark_approved(agent_name, version, body.approved_by)
        return {"ok": True, "version": row}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/versions/{agent_name}/{version}/canary")
async def start_canary(
    agent_name: str,
    version: str,
    body: CanaryIn = CanaryIn(),
    _user: dict = Depends(require_role("admin")),
):
    from graph_engine.agent_versioning import get_registry
    try:
        row = get_registry().start_canary(agent_name, version, body.percentage)
        return {"ok": True, "version": row}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.patch("/agents/versions/{agent_name}/{version}/promote")
async def promote_canary(
    agent_name: str,
    version: str,
    body: ApproveIn = ApproveIn(),
    _user: dict = Depends(require_role("admin")),
):
    from graph_engine.agent_versioning import get_registry
    try:
        row = get_registry().promote_canary(agent_name, version, body.approved_by)
        return {"ok": True, "version": row}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/agents/versions/{agent_name}/rollback")
async def rollback_agent(
    agent_name: str,
    _user: dict = Depends(require_role("admin")),
):
    from graph_engine.agent_versioning import get_registry
    try:
        row = get_registry().rollback(agent_name)
        return {"ok": True, "rolled_back_to": row}
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
