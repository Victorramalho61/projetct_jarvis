"""Import da planilha 'Controle de Vagas' — upsert por número de requisição.

Lê a mesma aba/cabeçalho da planilha real da equipe de RH (aba "Controle de
Vagas", cabeçalho na linha 15 -> header=14 no pandas) e faz upsert em
rh_vagas: se o número de requisição já existe, atualiza status/etapa/datas/
candidato/demais campos; se não existe, insere uma linha nova preservando o
número de requisição da planilha.
"""
import io
import re
from datetime import date, datetime

import pandas as pd

_SHEET = "Controle de Vagas"
_HEADER_ROW = 14  # linha 15 da planilha (0-indexed)

_CORRECOES_EMPRESA = {"VTC LOG": "VTCLOG"}

# Modelo novo (2026-09): aba em maiúsculas, cabeçalho na linha 1, SLA por fase
_SHEET_NOVO = "CONTROLE DE VAGAS"
_SHEET_SLA = "SLA"
_SHEET_LISTAS = "LISTAS SUSPENSAS"
_MAX_LINHAS_SLA = 5000
_STATUS_NOVO = {
    "ABERTA": "EM ANDAMENTO",
    "PREENCHIDA/FECHADA": "CONCLUÍDO",
    "CANCELADA": "CANCELADO",
    "EM STANDBY": "CONGELADO",
}
_CORRECOES_ETAPA = {
    "CONCLUIDO": "CONCLUÍDO",
    "RETORNO DO LIDER": "RETORNO DO LÍDER",
    "ENTREVISTA COM O LIDER": "ENTREVISTA COM O LÍDER",
    "APROVAÇÃO DO LIDER": "APROVAÇÃO DO LÍDER",
}
# Nº de requisição válido: TUR.ADM.281/26 (aceita TUR.ADM.290.26, digitado com ponto)
_RE_REQUISICAO = re.compile(r"^[A-Z]{3}\.ADM\.\d{3}[./]\d{2}$")
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
        abas = pd.ExcelFile(io.BytesIO(conteudo)).sheet_names
    except Exception:
        abas = []
    if _SHEET_NOVO in abas:
        from services.sla import invalidar_referencias

        try:
            return _importar_modelo_novo(sb, conteudo, nome_arquivo, user)
        finally:
            invalidar_referencias()

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


# ── Modelo novo ───────────────────────────────────────────────────────────────

def _upper(val) -> str | None:
    s = _clean_str(val)
    return " ".join(s.upper().split()) if s else None


def _int(val) -> int | None:
    try:
        return None if val is None or pd.isna(val) else int(val)
    except (TypeError, ValueError):
        return None


def _iso(val) -> str | None:
    d = _clean_date(val)
    return d.isoformat() if d and 2015 <= d.year <= 2100 else None


def _importar_tabela_sla(sb, xls: pd.ExcelFile) -> int:
    """Aba SLA -> rh_sla_cargos. Cargos repetidos com SLA diferente: vale a 1ª linha
    (mesmo critério do PROCV da planilha)."""
    from services.sla import normalizar_cargo

    if _SHEET_SLA not in xls.sheet_names:
        return 0
    # A aba SLA vem com a dimensão "cheia" do Excel (1.048.576 linhas) — sem nrows o pandas
    # materializa tudo e estoura a memória do container.
    bruto = pd.read_excel(xls, sheet_name=_SHEET_SLA, header=None, nrows=20)
    linha_header = next(
        (i for i, r in bruto.iterrows() if str(r.iloc[0]).strip().upper() == "CARGO"), None
    )
    if linha_header is None:
        return 0
    df = pd.read_excel(xls, sheet_name=_SHEET_SLA, header=linha_header, nrows=_MAX_LINHAS_SLA)
    df.columns = [str(c).strip().upper() for c in df.columns]
    vistos: dict[str, dict] = {}
    for _, r in df.iterrows():
        cargo = normalizar_cargo(_clean_str(r.get("CARGO")))
        if not cargo or cargo in vistos:
            continue
        vistos[cargo] = {
            "cargo_nome": cargo,
            "nivel": _upper(r.get("TIPO")),
            "rs": _int(r.get("R&S")),
            "link": _int(r.get("S LINK ADMISSIONAL")),
            "exames": _int(r.get("EXAMES")),
            "documentos": _int(r.get("ENTREGA DE DOCUMENTOS AO DP")),
            "empresa": _upper(r.get("EMPRESA")),
            "updated_at": datetime.utcnow().isoformat(),
        }
    linhas = list(vistos.values())
    for i in range(0, len(linhas), 200):
        sb.table("rh_sla_cargos").upsert(linhas[i:i + 200], on_conflict="cargo_nome").execute()
    return len(linhas)


def _sincronizar_listas(sb, xls: pd.ExcelFile, cache: "_LookupCache") -> int:
    """Aba LISTAS SUSPENSAS -> tabelas de lookup (só acrescenta; nunca apaga)."""
    if _SHEET_LISTAS not in xls.sheet_names:
        return 0
    df = pd.read_excel(xls, sheet_name=_SHEET_LISTAS, header=0, nrows=_MAX_LINHAS_SLA)
    df.columns = [str(c).strip().upper() for c in df.columns]
    mapa = {
        "EMPRESAS DO GRUPO": ("rh_empresas", "nome"),
        "UF": ("rh_ufs", "sigla"),
        "ALOCAÇÃO REAL": ("rh_alocacoes", "nome"),
        "TIPO DO CONTRATO": ("rh_tipos_contrato", "nome"),
        "TIPO DA VAGA": ("rh_tipos_vaga", "nome"),
        "HIERARQUIA": ("rh_hierarquias", "nome"),
        "RECRUTADORES RESPONSÁVEIS": ("rh_analistas", "nome"),
        "REQUISITANTES": ("rh_requisitantes", "nome"),
    }
    total = 0
    for coluna, (tabela, campo) in mapa.items():
        if coluna not in df.columns:
            continue
        for val in df[coluna].dropna().unique():
            if cache.get_or_create(tabela, campo, _upper(val)):
                total += 1
    # Cargo -> nível padrão (preenche o NÍVEL automático no Jarvis)
    if "CARGO" in df.columns and "NÍVEL" in df.columns:
        for _, r in df[["CARGO", "NÍVEL"]].dropna(subset=["CARGO"]).iterrows():
            cargo, nivel = _upper(r["CARGO"]), _upper(r["NÍVEL"])
            if not cargo:
                continue
            cargo_id = cache.get_or_create("rh_cargos", "nome", cargo)
            if nivel in ("OPERACIONAL", "TÁTICO", "ESTRATÉGICO"):
                nivel_id = cache.get_or_create("rh_niveis", "nome", nivel)
                sb.table("rh_cargos").update({"nivel_padrao_id": nivel_id}).eq("id", cargo_id).is_(
                    "nivel_padrao_id", "null"
                ).execute()
            total += 1
    return total


def _importar_modelo_novo(sb, conteudo: bytes, nome_arquivo: str, user: dict, dry_run: bool = False) -> dict:
    from routes.vagas import registrar_troca_etapa
    from services.numbering import gerar_numero_requisicao

    xls = pd.ExcelFile(io.BytesIO(conteudo))
    df = pd.read_excel(xls, sheet_name=_SHEET_NOVO, header=0, nrows=_MAX_LINHAS_SLA)
    df.columns = [str(c).strip().upper() for c in df.columns]
    df = df[df["Nº REQUISIÇÃO"].notna() | df["CARGO / VAGA"].notna()]
    # Linhas com nº válido primeiro: o nº gerado para as inválidas (PJ, "VTC GRU"...) nunca
    # pode ocupar um número real que ainda viria mais abaixo na planilha.
    _valido = df["Nº REQUISIÇÃO"].map(
        lambda v: bool(_RE_REQUISICAO.match(str(v).upper().replace(" ", ""))) if pd.notna(v) else False
    )
    df = pd.concat([df[_valido], df[~_valido]])

    cache = _LookupCache(sb)
    sla_cargos = listas = 0
    if not dry_run:
        sla_cargos = _importar_tabela_sla(sb, xls)
        listas = _sincronizar_listas(sb, xls, cache)

    status_map = {s["nome"]: s["id"] for s in sb.table("rh_status_vaga").select("id,nome").execute().data}
    etapas = {
        e["nome"]: e
        for e in sb.table("rh_etapas_processo").select("id,nome,ativo,secao_responsavel_id").execute().data
    }

    inseridas = atualizadas = com_erro = 0
    erros, previa = [], []

    for idx, row in df.iterrows():
        linha_planilha = idx + 2
        try:
            abertura = _iso(row.get("DATA DE ABERTURA"))
            if not abertura:
                erros.append({"linha": linha_planilha, "motivo": "Sem DATA DE ABERTURA válida — linha ignorada"})
                com_erro += 1
                continue

            req_original = _clean_str(row.get("Nº REQUISIÇÃO"))
            req = req_original.upper().replace(" ", "") if req_original else None
            req_invalido = not req or not _RE_REQUISICAO.match(req)

            empresa_nome = _upper(row.get("EMPRESA")) or "NÃO INFORMADO"
            empresa_nome = _CORRECOES_EMPRESA.get(empresa_nome, empresa_nome)
            empresa_id = cache.get_or_create("rh_empresas", "nome", empresa_nome)

            status_planilha = _upper(row.get("STATUS POR VAGA")) or "ABERTA"
            status_nome = _STATUS_NOVO.get(status_planilha, status_planilha)
            status_id = status_map.get(status_nome) or cache.get_or_create("rh_status_vaga", "nome", status_nome)

            etapa_nome = _upper(row.get("FUNIL DE VAGAS"))
            etapa_nome = _CORRECOES_ETAPA.get(etapa_nome, etapa_nome)
            etapa = etapas.get(etapa_nome) if etapa_nome else None
            if etapa_nome and not etapa:
                erros.append({"linha": linha_planilha, "motivo": f"Etapa '{etapa_nome}' não existe no funil — etapa não atualizada"})

            secao_nome = _upper(row.get("SEÇÃO RESPONSÁVEL"))
            secao_id = (
                cache.get_or_create("rh_secoes", "nome", secao_nome)
                if secao_nome and secao_nome != "NÃO MAPEADO"
                else (etapa or {}).get("secao_responsavel_id")
            )

            def _lk(tabela, coluna):
                v = _upper(row.get(coluna))
                return cache.get_or_create(tabela, "nome", v) if v else None

            sla_rs = _int(row.get("SLA R&S (DIAS)"))
            sla_adm = _int(row.get("SLA ADMISSÃO (DIAS)"))
            observacoes = _clean_str(row.get("OBSERVAÇÕES"))
            if req_invalido and req_original:
                marca = f"Nº original na planilha: {req_original}"
                observacoes = f"{marca} | {observacoes}" if observacoes else marca

            payload = {
                "empresa_id": empresa_id,
                "uf": _upper(row.get("UF")),
                "alocacao_id": _lk("rh_alocacoes", "ALOCAÇÃO REAL"),
                "cargo_id": _lk("rh_cargos", "CARGO / VAGA"),
                "nivel_id": _lk("rh_niveis", "NÍVEL"),
                "centro_custo": _upper(row.get("CENTRO DE CUSTO")),
                "hierarquia_id": _lk("rh_hierarquias", "HIERARQUIA"),
                "tipo_contrato_id": _lk("rh_tipos_contrato", "TIPO DE CONTRATO"),
                "tipo_vaga_id": _lk("rh_tipos_vaga", "TIPO DA VAGA"),
                "nome_substituido": _upper(row.get("NOME DO SUBSTITUIDO")),
                "requisitante_id": _lk("rh_requisitantes", "REQUISITANTE / GESTOR"),
                "responsavel_id": _lk("rh_analistas", "RECRUTADOR RESPONSÁVEL"),
                "status_id": status_id,
                "etapa_atual_id": (etapa or {}).get("id"),
                "secao_id": secao_id,
                "data_recebimento": abertura,
                "sla_rs_dias": sla_rs,
                "sla_admissao_dias": sla_adm,
                "sla_alvo_dias": (sla_rs or 0) + (sla_adm or 0) or None,
                "data_fechamento_rs": _iso(row.get("DATA DE FECHAMENTO DO R&S")),
                "data_confirmacao_contratacao": _iso(row.get("CONFIRMAÇÃO DE CONTRATAÇÃO")),
                "data_admissao": _iso(row.get("DATA DE ADMISSÃO")),
                "observacoes": observacoes,
                "data_inicio_etapa": _iso(row.get("DATA INÍCIO ETAPA ATUAL")),
                "sla_etapa_externa_dias": _int(row.get("SLA ETAPA EXTERNA (DIAS)")),
                "updated_by": user.get("id"),
                "updated_at": datetime.utcnow().isoformat(),
            }
            payload = {k: v for k, v in payload.items() if v is not None}

            existente = None
            if not req_invalido:
                r = sb.table("rh_vagas").select("id,etapa_atual_id").eq("numero_requisicao", req).execute()
                existente = r.data[0] if r.data else None
            elif req_original:
                # reimport: nº já gerado antes pra esse texto (marca nas observações)?
                r = sb.table("rh_vagas").select("id,etapa_atual_id").ilike(
                    "observacoes", f"Nº original na planilha: {req_original}%"
                ).eq("data_recebimento", abertura).execute()
                existente = r.data[0] if r.data else None
                if not existente and payload.get("cargo_id"):
                    # vaga já cadastrada com sufixo (ex.: "PJ" da planilha = "PJ-024" no Jarvis,
                    # da correção de duplicados): mesmo prefixo + abertura + cargo, match único
                    r = sb.table("rh_vagas").select("id,etapa_atual_id").ilike(
                        "numero_requisicao", f"{req_original}%"
                    ).eq("data_recebimento", abertura).eq("cargo_id", payload["cargo_id"]).execute()
                    existente = r.data[0] if len(r.data or []) == 1 else None
                if existente:
                    # vaga existente mantém as observações dela (sem a marca de nº gerado)
                    payload["observacoes"] = _clean_str(row.get("OBSERVAÇÕES"))
                    if payload["observacoes"] is None:
                        payload.pop("observacoes")

            etapa_mudou = bool(payload.get("etapa_atual_id")) and payload["etapa_atual_id"] != (existente or {}).get("etapa_atual_id")
            if etapa_mudou:
                payload.setdefault("data_inicio_etapa", date.today().isoformat())

            if dry_run:
                previa.append({
                    "linha": linha_planilha, "req": req_original,
                    "acao": "atualizar" if existente else "inserir",
                    "req_gerado": req_invalido, "status": status_nome, "etapa": (etapa or {}).get("nome"),
                })
                continue

            if existente:
                sb.table("rh_vagas").update(payload).eq("id", existente["id"]).execute()
                vaga_id = existente["id"]
                atualizadas += 1
            else:
                payload["numero_requisicao"] = req if not req_invalido else gerar_numero_requisicao(sb, empresa_id)
                payload["created_by"] = user.get("id")
                vaga_id = sb.table("rh_vagas").insert(payload).execute().data[0]["id"]
                inseridas += 1

            if etapa_mudou:
                registrar_troca_etapa(sb, vaga_id, payload["etapa_atual_id"], payload["data_inicio_etapa"])

        except Exception as exc:
            com_erro += 1
            erros.append({"linha": linha_planilha, "motivo": str(exc)[:200]})

    if dry_run:
        return {"previa": previa, "erros": erros}

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
        "sla_cargos_importados": sla_cargos,
        "itens_de_lista_sincronizados": listas,
        "erros": erros,
    }
