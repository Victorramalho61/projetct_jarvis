"""Geração automática do número de requisição (ex.: TUR.ADM.281/26)."""
import datetime
import re


def gerar_numero_requisicao(sb, empresa_id: str) -> str:
    empresa = sb.table("rh_empresas").select("prefixo_requisicao").eq("id", empresa_id).single().execute()
    prefixo = (empresa.data or {}).get("prefixo_requisicao") or "REQ"

    ano = datetime.date.today().year % 100
    # Próximo sequencial = maior já usado no prefixo/ano (+1). Contar vagas da empresa
    # colidia com números reais da planilha (várias empresas compartilham prefixo, ex. VTC).
    usados = sb.table("rh_vagas").select("numero_requisicao").like(
        "numero_requisicao", f"{prefixo}.ADM.%"
    ).execute().data or []
    seqs = [
        int(m.group(1)) for r in usados
        if (m := re.match(rf"^{re.escape(prefixo)}\.ADM\.(\d+)[./]{ano:02d}$", r["numero_requisicao"] or ""))
    ]
    seq = max(seqs, default=0) + 1

    numero = f"{prefixo}.ADM.{seq:03d}/{ano:02d}"
    # Colisão é improvável (contagem cumulativa por empresa), mas numero_requisicao
    # é UNIQUE — em caso de corrida, avança o sequencial até achar um livre.
    while sb.table("rh_vagas").select("id").eq("numero_requisicao", numero).execute().data:
        seq += 1
        numero = f"{prefixo}.ADM.{seq:03d}/{ano:02d}"
    return numero
