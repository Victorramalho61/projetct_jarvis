"""
Governança de Contratos — endpoints REST.

Todos os endpoints aplicam @limiter.limit() escalonado conforme custo da operação:
  - Endpoints que consultam Benner SQL Server: 10/minute (pesados)
  - Endpoint de descoberta: 5/minute (query agregada mais pesada)
  - Endpoints Supabase apenas: 20–60/minute
"""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import require_role
from limiter import limiter
from services.governance import (
    check_payment_adherence,
    compute_contract_divergences,
    create_contract,
    create_occurrence,
    create_sla_violation,
    fetch_benner_contracts_discovery,
    fetch_contract_payments_by_docmatch,
    fetch_contract_payments_by_handle,
    get_contract,
    get_governance_kpis,
    list_contracts,
    list_occurrences,
    list_sla_violations,
    update_contract,
    update_occurrence,
)

router = APIRouter(prefix="/expenses/governance", tags=["governance"])
logger = logging.getLogger(__name__)


# ── Request models ─────────────────────────────────────────────────────────────

class ContractCreate(BaseModel):
    titulo: str
    fornecedor_nome: str
    valor_total: float
    data_inicio: str
    data_fim: str
    modalidade: str = "servico"
    status: str = "vigente"
    numero: str | None = None
    fornecedor_benner_handle: int | None = None
    benner_documento_match: str | None = None
    valor_mensal: float | None = None
    qtd_parcelas: int | None = None
    objeto: str | None = None
    sla_config: list[dict] = []
    observacoes: str | None = None


class ContractUpdate(BaseModel):
    titulo: str | None = None
    fornecedor_nome: str | None = None
    valor_total: float | None = None
    data_inicio: str | None = None
    data_fim: str | None = None
    modalidade: str | None = None
    status: str | None = None
    numero: str | None = None
    fornecedor_benner_handle: int | None = None
    benner_documento_match: str | None = None
    valor_mensal: float | None = None
    qtd_parcelas: int | None = None
    objeto: str | None = None
    sla_config: list[dict] | None = None
    observacoes: str | None = None


class OccurrenceCreate(BaseModel):
    tipo: str
    descricao: str
    data_ocorrencia: str
    valor: float | None = None
    competencia: str | None = None
    status: str = "pendente"
    email_destinatarios: list[str] | None = None


class OccurrenceUpdate(BaseModel):
    status: str | None = None
    valor: float | None = None
    descricao: str | None = None
    email_enviado: bool | None = None
    email_assunto: str | None = None
    email_corpo: str | None = None
    email_destinatarios: list[str] | None = None
    email_enviado_at: str | None = None


class SLAViolationCreate(BaseModel):
    sla_metrica: str
    valor_contratado: float
    valor_medido: float
    periodo: str
    impacto: str | None = None
    penalidade_valor: float | None = None
    status: str = "registrado"


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/dashboard")
@limiter.limit("60/minute")
async def governance_dashboard(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """KPIs gerenciais: contratos vigentes, vencendo, ocorrências pendentes."""
    from services.sync import get_cached_governance_dashboard
    try:
        cached = get_cached_governance_dashboard()
        if cached:
            return cached
        return get_governance_kpis()
    except Exception as exc:
        logger.exception("Erro ao buscar dashboard de governança: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao calcular KPIs de governança.")


@router.get("/contracts")
@limiter.limit("60/minute")
async def list_contracts_endpoint(
    request: Request,
    status: str | None = None,
    _: dict = Depends(require_role("admin")),
):
    """Lista contratos cadastrados no Supabase."""
    try:
        return list_contracts(status=status)
    except Exception as exc:
        logger.exception("Erro ao listar contratos: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao listar contratos.")


@router.post("/contracts")
@limiter.limit("20/minute")
async def create_contract_endpoint(
    request: Request,
    body: ContractCreate,
    current_user: dict = Depends(require_role("admin")),
):
    """Cadastra novo contrato."""
    try:
        data = body.model_dump(exclude_none=True)
        data["created_by"] = current_user.get("sub")
        return create_contract(data)
    except Exception as exc:
        logger.exception("Erro ao criar contrato: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao criar contrato.")


@router.get("/contracts/{contract_id}")
@limiter.limit("30/minute")
async def get_contract_endpoint(
    request: Request,
    contract_id: str,
    _: dict = Depends(require_role("admin")),
):
    """Detalhe do contrato + itens + pagamentos Benner mesclados."""
    try:
        c = get_contract(contract_id)
        if not c:
            raise HTTPException(status_code=404, detail="Contrato não encontrado.")
        return c
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao buscar contrato %s: %s", contract_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao buscar contrato.")


@router.put("/contracts/{contract_id}")
@limiter.limit("20/minute")
async def update_contract_endpoint(
    request: Request,
    contract_id: str,
    body: ContractUpdate,
    _: dict = Depends(require_role("admin")),
):
    """Atualiza dados de um contrato."""
    try:
        data = body.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
        return update_contract(contract_id, data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao atualizar contrato %s: %s", contract_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao atualizar contrato.")


@router.get("/contracts/{contract_id}/payments")
@limiter.limit("10/minute")
async def get_contract_payments(
    request: Request,
    contract_id: str,
    _: dict = Depends(require_role("admin")),
):
    """Pagamentos históricos no Benner para este contrato (SQL Server — pesado)."""
    try:
        from services.governance import get_contract as _get
        c = _get(contract_id)
        if not c:
            raise HTTPException(status_code=404, detail="Contrato não encontrado.")
        if c.get("fornecedor_benner_handle"):
            return await asyncio.to_thread(fetch_contract_payments_by_handle, int(c["fornecedor_benner_handle"]))
        if c.get("benner_documento_match"):
            return await asyncio.to_thread(fetch_contract_payments_by_docmatch, c["benner_documento_match"])
        return []
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao buscar pagamentos Benner para contrato %s: %s", contract_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao buscar pagamentos no Benner.")


@router.get("/contracts/{contract_id}/divergences")
@limiter.limit("10/minute")
async def get_contract_divergences(
    request: Request,
    contract_id: str,
    _: dict = Depends(require_role("admin")),
):
    """Confronto previsto (contrato) vs realizado (Benner) por mês (SQL Server — pesado)."""
    try:
        return await asyncio.to_thread(compute_contract_divergences, contract_id)
    except Exception as exc:
        logger.exception("Erro ao calcular divergências do contrato %s: %s", contract_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao calcular divergências.")


@router.post("/contracts/{contract_id}/occurrences")
@limiter.limit("20/minute")
async def create_occurrence_endpoint(
    request: Request,
    contract_id: str,
    body: OccurrenceCreate,
    current_user: dict = Depends(require_role("admin")),
):
    """Registra glosa, multa, desconto, acréscimo ou notificação."""
    try:
        data = body.model_dump(exclude_none=True)
        data["created_by"] = current_user.get("sub")
        return create_occurrence(contract_id, data)
    except Exception as exc:
        logger.exception("Erro ao criar ocorrência: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao registrar ocorrência.")


@router.patch("/contracts/{contract_id}/occurrences/{occurrence_id}")
@limiter.limit("20/minute")
async def update_occurrence_endpoint(
    request: Request,
    contract_id: str,
    occurrence_id: str,
    body: OccurrenceUpdate,
    _: dict = Depends(require_role("admin")),
):
    """Atualiza status ou dados de e-mail de uma ocorrência."""
    try:
        data = body.model_dump(exclude_none=True)
        if not data:
            raise HTTPException(status_code=400, detail="Nenhum campo para atualizar.")
        return update_occurrence(occurrence_id, data)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Erro ao atualizar ocorrência %s: %s", occurrence_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao atualizar ocorrência.")


@router.get("/contracts/{contract_id}/occurrences")
@limiter.limit("30/minute")
async def list_occurrences_endpoint(
    request: Request,
    contract_id: str,
    status: str | None = None,
    _: dict = Depends(require_role("admin")),
):
    """Lista ocorrências de um contrato."""
    try:
        return list_occurrences(contract_id=contract_id, status=status)
    except Exception as exc:
        logger.exception("Erro ao listar ocorrências: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao listar ocorrências.")


@router.get("/contracts/{contract_id}/sla")
@limiter.limit("30/minute")
async def list_sla_violations_endpoint(
    request: Request,
    contract_id: str,
    _: dict = Depends(require_role("admin")),
):
    """Lista violações de SLA de um contrato."""
    try:
        return list_sla_violations(contract_id=contract_id)
    except Exception as exc:
        logger.exception("Erro ao listar violações SLA: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao listar violações SLA.")


@router.post("/contracts/{contract_id}/sla")
@limiter.limit("20/minute")
async def create_sla_violation_endpoint(
    request: Request,
    contract_id: str,
    body: SLAViolationCreate,
    current_user: dict = Depends(require_role("admin")),
):
    """Registra violação de SLA."""
    try:
        data = body.model_dump(exclude_none=True)
        data["created_by"] = current_user.get("sub")
        return create_sla_violation(contract_id, data)
    except Exception as exc:
        logger.exception("Erro ao registrar violação SLA: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao registrar violação SLA.")


@router.post("/contracts/{contract_id}/check-adherence")
@limiter.limit("10/minute")
async def check_contract_adherence(
    request: Request,
    contract_id: str,
    _: dict = Depends(require_role("admin")),
):
    """
    Verifica aderência dos pagamentos Benner ao contrato.
    Auto-registra ocorrências para divergências (valor a maior / a menor).
    """
    try:
        return check_payment_adherence(contract_id)
    except Exception as exc:
        logger.exception("Erro ao verificar aderência do contrato %s: %s", contract_id, exc)
        raise HTTPException(status_code=500, detail="Erro ao verificar aderência.")


@router.post("/discover")
@limiter.limit("5/minute")
async def discover_benner_contracts(
    request: Request,
    _: dict = Depends(require_role("admin")),
):
    """
    Auto-descoberta de contratos no Benner via CP_RECEBIMENTOFISICO.CONTRATO.
    Query pesada no SQL Server — limitada a 5 req/min.
    """
    try:
        return fetch_benner_contracts_discovery()
    except Exception as exc:
        logger.exception("Erro ao descobrir contratos no Benner: %s", exc)
        raise HTTPException(status_code=500, detail="Erro ao consultar Benner.")
