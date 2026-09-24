"""SLA das vagas em duas fases — fonte única usada por listagem, dashboard e relatório semanal.

- R&S: Data de Abertura (data_recebimento) → Data de Fechamento do R&S.
  SLA = sla_rs_dias da vaga, senão coluna R&S da aba SLA (rh_sla_cargos) pelo cargo.
- Admissão: Confirmação de Contratação (Solicitação Link Admissional) → Data de Admissão
  (entrega de documentação). SLA = sla_admissao_dias, senão Link + Exames + Documentos do cargo.
- Etapa atual: etapas externas (Líder/DP/SESMT) têm prazo próprio (3 dias, planilha
  "SLA ETAPA EXTERNA"), limitado ao prazo da fase; etapas do RH não são cobradas separadas.

Vagas históricas (anteriores ao modelo novo, sem sla_rs_dias nem data de fechamento do R&S)
que já foram concluídas usam a data de admissão como fim e o SLA total (sla_alvo_dias),
marcadas com estimado=True — mantém o histórico no painel sem inventar precisão.
Dias sempre corridos, igual à planilha.
"""
from datetime import date, datetime, timedelta
from typing import Optional

NO_PRAZO = "NO PRAZO"
ATRASADO = "ATRASADO"
CONCLUIDA_NO_PRAZO = "CONCLUÍDA NO PRAZO"
CONCLUIDA_COM_ATRASO = "CONCLUÍDA COM ATRASO"
CANCELADA = "CANCELADA"
CONGELADA = "CONGELADA (SLA PAUSADO)"
NAO_INICIADA = "NÃO INICIADA"
FALTA_FECHAMENTO_RS = "FALTA DATA DE FECHAMENTO DO R&S"
FALTA_INICIO_ADM = "FALTA DATA DE INÍCIO DA ADMISSÃO"
INFORMAR_INICIO_ETAPA = "INFORMAR DATA DE INÍCIO"
SEM_DADOS = "SEM DADOS"
DATAS_INCONSISTENTES = "DATAS INCONSISTENTES"

# Status que entram no % no prazo (o resto é informativo)
AVALIAVEIS = {NO_PRAZO, ATRASADO, CONCLUIDA_NO_PRAZO, CONCLUIDA_COM_ATRASO}
NO_PRAZO_SET = {NO_PRAZO, CONCLUIDA_NO_PRAZO}

SLA_ETAPA_EXTERNA_PADRAO = 3


def normalizar_cargo(nome: Optional[str]) -> str:
    return " ".join((nome or "").upper().split())


def _d(v) -> Optional[date]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    try:
        return datetime.strptime(str(v)[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _fase(inicio: Optional[date], fim: Optional[date], sla: Optional[int], hoje: date,
          pausa: Optional[str] = None, estimado: bool = False) -> dict:
    limite = inicio + timedelta(days=sla) if inicio and sla is not None else None
    dias = None
    if inicio:
        dias = ((fim or hoje) - inicio).days
        if dias < 0:
            dias = None

    if pausa:
        status = pausa
    elif inicio and fim and fim < inicio:
        status = DATAS_INCONSISTENTES  # ex.: data de admissão anterior à confirmação
    elif not inicio or sla is None:
        status = SEM_DADOS
    elif fim:
        status = CONCLUIDA_NO_PRAZO if fim <= limite else CONCLUIDA_COM_ATRASO
    else:
        status = NO_PRAZO if hoje <= limite else ATRASADO

    return {
        "inicio": inicio.isoformat() if inicio else None,
        "fim": fim.isoformat() if fim else None,
        "sla": sla,
        "limite": limite.isoformat() if limite else None,
        "dias": dias,
        "status": status,
        "estimado": estimado,
    }


def calc_sla(v: dict, sla_cargos: dict, etapas: dict, hoje: Optional[date] = None) -> dict:
    """v: linha de rh_vagas já serializada (status/etapa como nomes + flags).
    sla_cargos: {cargo_normalizado: {rs, link, exames, documentos}}.
    etapas: {etapa_id: {nome, fase, externa}}."""
    hoje = hoje or date.today()
    status = v.get("status") or ""
    concluido = bool(v.get("status_concluido"))
    cancelada = status == "CANCELADO"
    congelada = status in ("CONGELADO", "EM STANDBY")
    etapa = etapas.get(v.get("etapa_atual_id")) or {}
    fase_etapa = etapa.get("fase")

    cargo_sla = sla_cargos.get(normalizar_cargo(v.get("cargo"))) or {}
    abertura = _d(v.get("data_recebimento"))
    fech_rs = _d(v.get("data_fechamento_rs"))
    conf = _d(v.get("data_confirmacao_contratacao"))
    admissao = _d(v.get("data_admissao"))
    modelo_novo = v.get("sla_rs_dias") is not None or fech_rs is not None or conf is not None

    pausa = CANCELADA if cancelada else CONGELADA if congelada else None

    # ── R&S ──
    sla_rs = v.get("sla_rs_dias")
    if sla_rs is None:
        sla_rs = cargo_sla.get("rs")
    estimado = False
    fim_rs = fech_rs
    if not fim_rs and conf:
        fim_rs = conf  # já entrou na admissão: R&S terminou na confirmação
    if not fim_rs and concluido:
        if not modelo_novo and admissao:
            # histórico: só temos a data de admissão — compara com o SLA total da vaga
            fim_rs = admissao
            estimado = True
            if v.get("sla_alvo_dias"):
                sla_rs = v.get("sla_alvo_dias")
    rs = _fase(abertura, fim_rs, sla_rs, hoje, pausa=pausa, estimado=estimado)
    if not pausa and concluido and not fim_rs:
        rs["status"] = FALTA_FECHAMENTO_RS

    # ── Admissão ──
    sla_adm = v.get("sla_admissao_dias")
    if sla_adm is None and cargo_sla:
        sla_adm = sum(cargo_sla.get(k) or 0 for k in ("link", "exames", "documentos")) or None
    adm = _fase(conf, admissao if conf else None, sla_adm, hoje, pausa=pausa)
    if not pausa and not conf:
        em_admissao = fase_etapa == "ADMISSAO" or bool(fech_rs) or (concluido and modelo_novo)
        adm["status"] = FALTA_INICIO_ADM if em_admissao else NAO_INICIADA
        adm["sla"] = sla_adm

    # ── Etapa atual (só etapas externas têm prazo próprio) ──
    etapa_info = {
        "nome": etapa.get("nome"), "fase": fase_etapa, "externa": bool(etapa.get("externa")),
        "inicio": None, "dias": None, "sla": None, "limite": None, "status": None,
    }
    inicio_etapa = _d(v.get("data_inicio_etapa"))
    if inicio_etapa and fase_etapa in ("RS", "ADMISSAO"):
        etapa_info["inicio"] = inicio_etapa.isoformat()
        etapa_info["dias"] = max((hoje - inicio_etapa).days, 0)
    if etapa.get("externa") and fase_etapa in ("RS", "ADMISSAO"):
        sla_ext = v.get("sla_etapa_externa_dias") or SLA_ETAPA_EXTERNA_PADRAO
        etapa_info["sla"] = sla_ext
        if pausa:
            etapa_info["status"] = pausa
        elif not inicio_etapa:
            etapa_info["status"] = INFORMAR_INICIO_ETAPA
        else:
            limite = inicio_etapa + timedelta(days=sla_ext)
            limite_fase = _d((adm if fase_etapa == "ADMISSAO" else rs).get("limite"))
            if limite_fase and limite_fase < limite:
                limite = limite_fase
            etapa_info["limite"] = limite.isoformat()
            etapa_info["status"] = NO_PRAZO if hoje <= limite else ATRASADO

    return {"rs": rs, "adm": adm, "etapa": etapa_info, "modelo_novo": modelo_novo}


def carregar_referencias(sb) -> tuple[dict, dict]:
    """(sla_cargos, etapas) — carregar uma vez por request."""
    from services.paginacao import buscar_todos

    sla_cargos = {
        r["cargo_nome"]: r
        for r in buscar_todos(lambda: sb.table("rh_sla_cargos").select("id,cargo_nome,rs,link,exames,documentos"))
    }
    etapas = {
        e["id"]: e
        for e in (sb.table("rh_etapas_processo").select("id,nome,ordem,fase,externa,ativo").execute().data or [])
    }
    return sla_cargos, etapas


_REF_CACHE: dict = {"ts": 0.0, "val": None}
_REF_TTL_S = 60


def referencias(sb) -> tuple[dict, dict]:
    """carregar_referencias com cache curto — _serialize roda por linha."""
    import time

    agora = time.monotonic()
    if _REF_CACHE["val"] is None or agora - _REF_CACHE["ts"] > _REF_TTL_S:
        _REF_CACHE["val"] = carregar_referencias(sb)
        _REF_CACHE["ts"] = agora
    return _REF_CACHE["val"]


def invalidar_referencias() -> None:
    _REF_CACHE["val"] = None
