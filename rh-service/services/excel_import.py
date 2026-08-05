"""Import da planilha 'Controle de Vagas' — upsert por número de requisição.

Lê a mesma aba/cabeçalho da planilha real da equipe de RH (aba "Controle de
Vagas", cabeçalho na linha 15 -> header=14 no pandas) e faz upsert em
rh_vagas: se o número de requisição já existe, atualiza status/etapa/datas/
candidato/demais campos; se não existe, insere uma linha nova preservando o
número de requisição da planilha.
"""
import io
from datetime import date, datetime

import pandas as pd

_SHEET = "Controle de Vagas"
_HEADER_ROW = 14  # linha 15 da planilha (0-indexed)

_CORRECOES_EMPRESA = {"VTC LOG": "VTCLOG"}
_CORRECOES_STATUS = {"CONCLUIDA": "CONCLUÍDO", "CONGELADA": "CONGELADO"}


class _LookupCache:
    """Evita repetir SELECT/INSERT para o mesmo valor dentro de um import."""

    def __init__(self, sb):
        self.sb = sb
        self._cache: dict[tuple, str | None] = {}

    def get_or_create(self, table: str, col: str, valor, extra: dict | None = None) -> str | None:
        if valor is None:
            return None
        valor = str(valor).strip()
        if not valor or valor.upper() in ("NAN", "NONE", "N/A"):
            return None

        key = (table, col, valor)
        if key in self._cache:
            return self._cache[key]

        existing = self.sb.table(table).select("id").eq(col, valor).execute()
        if existing.data:
            item_id = existing.data[0]["id"]
        else:
            row = {col: valor}
            if extra:
                row.update(extra)
            resp = self.sb.table(table).insert(row).execute()
            item_id = resp.data[0]["id"]

        self._cache[key] = item_id
        return item_id

    def lookup(self, table: str, col: str, valor) -> str | None:
        """Busca sem criar (usado para etapas do processo — lista fechada)."""
        if not valor:
            return None
        key = ("lookup", table, col, valor)
        if key in self._cache:
            return self._cache[key]
        resp = self.sb.table(table).select("id").eq(col, valor).execute()
        item_id = resp.data[0]["id"] if resp.data else None
        self._cache[key] = item_id
        return item_id


def _clean_str(val) -> str | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    s = str(val).strip()
    return s if s and s.upper() not in ("NAN", "NONE", "N/A") else None


def _clean_date(val):
    d = pd.to_datetime(val, errors="coerce")
    return None if pd.isna(d) else d.date()


def _ultima_etapa(texto: str | None) -> str | None:
    """'ETAPAS DO PROCESSO' vem como lista separada por ';' — usamos a última
    etapa mencionada como a etapa atual do processo."""
    if not texto:
        return None
    partes = [p.strip().rstrip(";").strip() for p in texto.split(";") if p.strip()]
    return partes[-1] if partes else None


def importar_planilha(sb, conteudo: bytes, nome_arquivo: str, user: dict) -> dict:
    try:
        df = pd.read_excel(io.BytesIO(conteudo), sheet_name=_SHEET, header=_HEADER_ROW)
    except Exception as exc:
        return {
            "upload_id": None, "linhas_processadas": 0, "linhas_inseridas": 0,
            "linhas_atualizadas": 0, "linhas_com_erro": 1,
            "erros": [{"linha": None, "motivo": f"Não foi possível ler a planilha: {exc}"}],
        }

    cache = _LookupCache(sb)
    status_map = {
        s["nome"]: s["id"] for s in sb.table("rh_status_vaga").select("id,nome").execute().data
    }
    tipo_vaga_map = {
        t["nome"]: t["id"] for t in sb.table("rh_tipos_vaga").select("id,nome").execute().data
    }

    inseridas = atualizadas = com_erro = 0
    erros = []

    for idx, row in df.iterrows():
        linha_planilha = idx + _HEADER_ROW + 2  # +2: header é a linha 15, dados começam na 16

        try:
            data_recebimento = _clean_date(row.get("DATA RECEBIMENTO"))
            if not data_recebimento or not (2015 <= data_recebimento.year <= 2100):
                erros.append({"linha": linha_planilha, "motivo": "Sem data de recebimento válida — linha ignorada"})
                com_erro += 1
                continue

            numero_requisicao = _clean_str(row.get("Nº DA REQUISIÇÃO"))

            empresa_nome = _clean_str(row.get("EMPRESA")) or "NÃO INFORMADO"
            empresa_nome = _CORRECOES_EMPRESA.get(empresa_nome.upper(), empresa_nome.upper())
            empresa_id = cache.get_or_create("rh_empresas", "nome", empresa_nome)

            status_nome = _clean_str(row.get("STATUS DA VAGA")) or "EM ANDAMENTO"
            status_nome = _CORRECOES_STATUS.get(status_nome.upper(), status_nome.upper())
            status_id = status_map.get(status_nome) or cache.get_or_create("rh_status_vaga", "nome", status_nome)

            tipo_vaga_nome = _clean_str(row.get("TIPO DA VAGA"))
            tipo_vaga_id = None
            if tipo_vaga_nome:
                tipo_vaga_id = tipo_vaga_map.get(tipo_vaga_nome.upper()) or cache.get_or_create(
                    "rh_tipos_vaga", "nome", tipo_vaga_nome.upper()
                )

            cargo_nome = _clean_str(row.get("CARGO"))
            cargo_id = cache.get_or_create("rh_cargos", "nome", cargo_nome.upper()) if cargo_nome else None

            nivel_nome = _clean_str(row.get("NÍVEL"))
            nivel_id = cache.get_or_create("rh_niveis", "nome", nivel_nome.upper()) if nivel_nome else None

            hierarquia_nome = _clean_str(row.get("HIERARQUIA"))
            hierarquia_id = cache.get_or_create("rh_hierarquias", "nome", hierarquia_nome.upper()) if hierarquia_nome else None

            requisitante_nome = _clean_str(row.get("REQUISITANTE (PRIMEIRO E ÚLTIMO NOME)"))
            requisitante_id = cache.get_or_create("rh_requisitantes", "nome", requisitante_nome.upper()) if requisitante_nome else None

            responsavel_nome = _clean_str(row.get("RESPONSÁVEL PELA VAGA")) or "NÃO INFORMADO"
            responsavel_id = cache.get_or_create("rh_analistas", "nome", responsavel_nome.upper())

            alocacao_nome = _clean_str(row.get("ALOCAÇÃO REAL"))
            alocacao_id = cache.get_or_create("rh_alocacoes", "nome", alocacao_nome.upper()) if alocacao_nome else None

            tipo_contrato_nome = _clean_str(row.get("TIPO DO CONTRATO"))
            tipo_contrato_id = cache.get_or_create("rh_tipos_contrato", "nome", tipo_contrato_nome.upper()) if tipo_contrato_nome else None

            secao_nome = _clean_str(row.get("SEÇÃO")) or "RH"
            secao_id = cache.get_or_create("rh_secoes", "nome", secao_nome.upper())

            etapa_nome = _ultima_etapa(_clean_str(row.get("ETAPAS DO PROCESSO")))
            etapa_id = cache.lookup("rh_etapas_processo", "nome", etapa_nome) if etapa_nome else None

            sla_raw = row.get("SLA")
            sla_alvo_dias = int(sla_raw) if sla_raw is not None and not pd.isna(sla_raw) else None

            payload = {
                "numero_requisicao": numero_requisicao,
                "empresa_id": empresa_id,
                "uf": _clean_str(row.get("UF")),
                "alocacao_id": alocacao_id,
                "tipo_contrato_id": tipo_contrato_id,
                "data_recebimento": data_recebimento.isoformat(),
                "data_aprovacao_diretoria": (_clean_date(row.get("DATA DA APROVAÇÃO DIRETORIA")) or None),
                "tipo_vaga_id": tipo_vaga_id,
                "cargo_id": cargo_id,
                "nivel_id": nivel_id,
                "hierarquia_id": hierarquia_id,
                "requisitante_id": requisitante_id,
                "status_id": status_id,
                "etapa_atual_id": etapa_id,
                "secao_id": secao_id,
                "responsavel_id": responsavel_id,
                "sla_alvo_dias": sla_alvo_dias,
                "justificativa": _clean_str(row.get("JUSTIFICATIVA")),
                "data_admissao": (_clean_date(row.get("DATA ADMISSÃO OU MOVIMENTAÇÃO")) or None),
                "candidato": _clean_str(row.get("CANDIDATO")),
                "updated_by": user.get("id"),
            }
            if payload["data_aprovacao_diretoria"]:
                payload["data_aprovacao_diretoria"] = payload["data_aprovacao_diretoria"].isoformat()
            if payload["data_admissao"]:
                payload["data_admissao"] = payload["data_admissao"].isoformat()
            payload = {k: v for k, v in payload.items() if v is not None}

            if numero_requisicao:
                existente = sb.table("rh_vagas").select("id").eq("numero_requisicao", numero_requisicao).execute()
            else:
                existente = None

            if existente and existente.data:
                sb.table("rh_vagas").update(payload).eq("id", existente.data[0]["id"]).execute()
                atualizadas += 1
            else:
                if not numero_requisicao:
                    from services.numbering import gerar_numero_requisicao
                    payload["numero_requisicao"] = gerar_numero_requisicao(sb, empresa_id)
                payload["created_by"] = user.get("id")
                sb.table("rh_vagas").insert(payload).execute()
                inseridas += 1

        except Exception as exc:
            com_erro += 1
            erros.append({"linha": linha_planilha, "motivo": str(exc)[:200]})

    registro = sb.table("rh_uploads").insert({
        "arquivo_nome": nome_arquivo,
        "usuario_id": user.get("id"),
        "usuario_nome": user.get("display_name") or user.get("username") or "desconhecido",
        "linhas_processadas": len(df),
        "linhas_inseridas": inseridas,
        "linhas_atualizadas": atualizadas,
        "linhas_com_erro": com_erro,
        "detalhes": erros[:500],
    }).execute()

    return {
        "upload_id": registro.data[0]["id"] if registro.data else None,
        "linhas_processadas": len(df),
        "linhas_inseridas": inseridas,
        "linhas_atualizadas": atualizadas,
        "linhas_com_erro": com_erro,
        "erros": erros,
    }
