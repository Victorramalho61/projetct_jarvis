from fastapi import APIRouter, Depends, HTTPException

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/api/support")


@router.get("/conversations")
def list_conversations(
    limit: int = 50,
    _user=Depends(require_role("admin", "support")),
):
    db = get_supabase()
    res = (
        db.table("support_conversations")
        .select("*")
        .order("updated_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


@router.get("/conversations/{conv_id}/messages")
def get_messages(
    conv_id: str,
    _user=Depends(require_role("admin", "support")),
):
    db = get_supabase()
    res = (
        db.table("support_messages")
        .select("*")
        .eq("conversation_id", conv_id)
        .order("created_at")
        .execute()
    )
    return res.data


@router.get("/tickets")
def list_tickets(
    limit: int = 50,
    _user=Depends(require_role("admin", "support")),
):
    db = get_supabase()
    res = (
        db.table("support_tickets")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


@router.get("/users")
def list_users(
    limit: int = 100,
    _user=Depends(require_role("admin", "support")),
):
    db = get_supabase()
    res = (
        db.table("support_users")
        .select("id,phone,name,email,company,location,profile_complete,created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data


@router.delete("/users/{user_id}")
def delete_user(
    user_id: str,
    _user=Depends(require_role("admin")),
):
    db = get_supabase()
    db.table("support_users").delete().eq("id", user_id).execute()
    return {"ok": True}
