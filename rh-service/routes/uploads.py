"""Auditoria de uploads em massa da planilha de vagas."""
from fastapi import APIRouter, Depends

from auth import require_role
from db import get_supabase

router = APIRouter(prefix="/api/rh/uploads")

_ROLES = ("admin", "rh")


def _require_rh(user=Depends(require_role(*_ROLES))):
    return user


@router.get("/ultimo")
def ultimo_upload(user=Depends(_require_rh)):
    sb = get_supabase()
    resp = sb.table("rh_uploads").select("*").order("criado_em", desc=True).limit(1).execute()
    return resp.data[0] if resp.data else None


@router.get("")
def historico_uploads(user=Depends(_require_rh)):
    sb = get_supabase()
    resp = sb.table("rh_uploads").select("*").order("criado_em", desc=True).limit(50).execute()
    return resp.data or []
