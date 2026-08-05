"""Geração automática do número de requisição (ex.: TUR.ADM.281/26)."""
import datetime


def gerar_numero_requisicao(sb, empresa_id: str) -> str:
    empresa = sb.table("rh_empresas").select("prefixo_requisicao").eq("id", empresa_id).single().execute()
    prefixo = (empresa.data or {}).get("prefixo_requisicao") or "REQ"

    ano = datetime.date.today().year % 100
    existentes = sb.table("rh_vagas").select("id", count="exact").eq("empresa_id", empresa_id).execute()
    seq = (existentes.count or 0) + 1

    numero = f"{prefixo}.ADM.{seq:03d}/{ano:02d}"
    # Colisão é improvável (contagem cumulativa por empresa), mas numero_requisicao
    # é UNIQUE — em caso de corrida, avança o sequencial até achar um livre.
    while sb.table("rh_vagas").select("id").eq("numero_requisicao", numero).execute().data:
        seq += 1
        numero = f"{prefixo}.ADM.{seq:03d}/{ano:02d}"
    return numero
