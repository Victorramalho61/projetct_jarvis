import uuid
from typing import Any, Iterator, Optional, Sequence, Tuple

from db import get_supabase


class JarvisCheckpointer:
    """Persiste checkpoints do LangGraph na tabela langgraph_checkpoints do Supabase."""

    def __init__(self):
        self._db = get_supabase()

    def put(self, thread_id: str, checkpoint_id: str, state: dict, metadata: dict | None = None, parent_id: str | None = None) -> None:
        self._db.table("langgraph_checkpoints").upsert({
            "thread_id": thread_id,
            "checkpoint_id": checkpoint_id,
            "parent_id": parent_id,
            "state": state,
            "metadata": metadata or {},
        }, on_conflict="thread_id,checkpoint_id").execute()

    def get(self, thread_id: str, checkpoint_id: str | None = None) -> dict | None:
        q = self._db.table("langgraph_checkpoints").select("*").eq("thread_id", thread_id)
        if checkpoint_id:
            q = q.eq("checkpoint_id", checkpoint_id)
        else:
            q = q.order("created_at", desc=True).limit(1)
        res = q.execute()
        return res.data[0] if res.data else None

    def list(self, thread_id: str, limit: int = 20) -> list[dict]:
        res = (
            self._db.table("langgraph_checkpoints")
            .select("*")
            .eq("thread_id", thread_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return res.data or []

    def create_thread(self, agent_id: str) -> str:
        thread_id = str(uuid.uuid4())
        self._db.table("langgraph_threads").insert({
            "agent_id": agent_id,
            "thread_id": thread_id,
            "status": "running",
        }).execute()
        return thread_id

    def update_thread_status(self, thread_id: str, status: str) -> None:
        from datetime import datetime, timezone
        self._db.table("langgraph_threads").update({
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("thread_id", thread_id).execute()
