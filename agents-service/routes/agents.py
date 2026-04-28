import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from auth import require_role
from db import get_supabase

logger = logging.getLogger(__name__)
router = APIRouter()


class AgentIn(BaseModel):
    name: str
    description: str = ""
    agent_type: Literal["freshservice_sync", "script"]
    config: dict = {}
    schedule_type: Literal["manual", "interval", "daily", "weekly", "monthly"] = "manual"
    schedule_config: dict = {}
    enabled: bool = True


class AgentPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    config: dict | None = None
    schedule_type: str | None = None
    schedule_config: dict | None = None
    enabled: bool | None = None


class ClaudeChatIn(BaseModel):
    message: str
    history: list[dict] = []


@router.get("/agents")
def list_agents(user=Depends(require_role("admin"))):
    db = get_supabase()
    return db.table("agents").select("*").order("created_at").execute().data


@router.post("/agents", status_code=201)
def create_agent(body: AgentIn, user=Depends(require_role("admin"))):
    db = get_supabase()
    payload = body.model_dump()
    payload["created_by"] = user["id"]
    agent = db.table("agents").insert(payload).execute().data[0]
    from services.scheduler import reload_agents
    reload_agents()
    return agent


@router.patch("/agents/{agent_id}")
def update_agent(agent_id: str, body: AgentPatch, user=Depends(require_role("admin"))):
    db = get_supabase()
    patch = {k: v for k, v in body.model_dump().items() if v is not None}
    agent = db.table("agents").update(patch).eq("id", agent_id).execute().data[0]
    from services.scheduler import reload_agents
    reload_agents()
    return agent


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: str, user=Depends(require_role("admin"))):
    db = get_supabase()
    db.table("agents").delete().eq("id", agent_id).execute()
    from services.scheduler import reload_agents
    reload_agents()


@router.post("/agents/{agent_id}/run")
async def run_agent_endpoint(
    agent_id: str, background_tasks: BackgroundTasks, user=Depends(require_role("admin"))
):
    db = get_supabase()
    rows = db.table("agents").select("*").eq("id", agent_id).execute().data
    if not rows:
        raise HTTPException(404, "Agente não encontrado")
    from services.agent_runner import run_agent
    background_tasks.add_task(run_agent, rows[0])
    return {"ok": True, "agent_id": agent_id}


@router.get("/agents/{agent_id}/runs")
def get_agent_runs(
    agent_id: str, limit: int = 20, offset: int = 0, user=Depends(require_role("admin"))
):
    db = get_supabase()
    return (
        db.table("agent_runs")
        .select("*")
        .eq("agent_id", agent_id)
        .order("started_at", desc=True)
        .limit(limit)
        .offset(offset)
        .execute()
        .data
    )


@router.post("/agents/claude/chat")
async def claude_chat(body: ClaudeChatIn, user=Depends(require_role("admin"))):
    db = get_supabase()
    profile = db.table("profiles").select("anthropic_api_key").eq("id", user["id"]).execute().data
    api_key = (profile[0].get("anthropic_api_key") or "").strip() if profile else ""
    if not api_key:
        raise HTTPException(
            400,
            "Configure sua chave Anthropic em Perfil antes de usar este recurso.",
        )
    from services.claude_agent_builder import chat
    return await chat(body.message, body.history, user, api_key)
