"""Motor RPA Benner — orquestra classificação + execução de handlers por erro.

ATIVAÇÃO MANUAL — este executor NÃO está agendado no scheduler.
Para ativar após validação com a equipe, adicionar em scheduler.py:
    from services.benner_rpa.executor import run_rpa_cycle
    _scheduler.add_job(run_rpa_cycle, CronTrigger(hour=11, minute=30, timezone="UTC"),
                       id="benner_rpa", replace_existing=True, max_instances=1)
"""
import asyncio
import logging
from datetime import timezone, datetime

logger = logging.getLogger(__name__)

_MAX_TENTATIVAS = 3


async def run_rpa_cycle() -> dict:
    """Executa um ciclo RPA: busca pendentes → classifica → aplica handler → atualiza status.

    Retorna sumário do ciclo: {processados, resolvidos, aguardando_input, erros}.
    """
    from db import get_supabase
    from benner_db import get_benner_conn
    from services.benner_classifier import classify
    from services.benner_rpa.handlers import HANDLERS

    sb = get_supabase()
    stats = {"processados": 0, "resolvidos": 0, "aguardando_input": 0, "erros": 0}

    # Busca erros pendentes com tentativas restantes
    try:
        resp = (
            sb.table("benner_erros")
            .select("*")
            .eq("rpa_status", "pendente")
            .lt("rpa_tentativas", _MAX_TENTATIVAS)
            .order("capturado_em", desc=False)
            .limit(200)
            .execute()
        )
        pendentes = resp.data or []
    except Exception as exc:
        logger.error("rpa_cycle: falha ao buscar pendentes: %s", exc)
        return stats

    if not pendentes:
        logger.info("rpa_cycle: nenhum erro pendente")
        return stats

    logger.info("rpa_cycle: processando %d erros pendentes", len(pendentes))

    # Abre conexão SQL Server para os handlers
    try:
        conn = await asyncio.to_thread(get_benner_conn)
    except Exception as exc:
        logger.error("rpa_cycle: falha ao conectar SQL Server: %s", exc)
        return stats

    for erro in pendentes:
        stats["processados"] += 1
        handle_id = erro["id"]
        categoria = erro.get("rpa_categoria") or classify(erro.get("mensagem"), erro.get("tipo_erro"))

        # Classifica se ainda não foi
        if not erro.get("rpa_categoria"):
            try:
                sb.table("benner_erros").update({"rpa_categoria": categoria}).eq("id", handle_id).execute()
            except Exception:
                pass

        handler_fn = HANDLERS.get(categoria, HANDLERS["outros"])

        try:
            resultado = await asyncio.to_thread(handler_fn, erro, conn)
        except Exception as exc:
            logger.error("rpa_cycle: handler '%s' erro inesperado (id=%d): %s", categoria, handle_id, exc)
            resultado = type("R", (), {"success": False, "detail": str(exc)})()

        nova_tentativa = (erro.get("rpa_tentativas") or 0) + 1
        agora = datetime.now(tz=timezone.utc).isoformat()

        if resultado.success:
            novo_status = "resolvido"
            stats["resolvidos"] += 1
        elif nova_tentativa >= _MAX_TENTATIVAS:
            novo_status = "aguardando_input"
            stats["aguardando_input"] += 1
        else:
            novo_status = "pendente"
            stats["erros"] += 1

        try:
            sb.table("benner_erros").update({
                "rpa_status":     novo_status,
                "rpa_categoria":  categoria,
                "rpa_tentativas": nova_tentativa,
                "rpa_ultima_acao": agora,
                "rpa_resultado":  resultado.detail,
            }).eq("id", handle_id).execute()
        except Exception as exc:
            logger.error("rpa_cycle: falha ao atualizar status id=%d: %s", handle_id, exc)

    conn.close()
    logger.info("rpa_cycle: ciclo concluído — %s", stats)
    return stats
