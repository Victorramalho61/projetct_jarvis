import logging
from typing import Any

_logger = logging.getLogger(__name__)


class ConferenceEngine:
    def __init__(self, sb):
        self.sb = sb

    def run(self, company_id: str, period_id: str) -> dict:
        from services.cfop_cst_tables import (
            is_cfop_entrada, is_cfop_saida, is_cst_pis_cofins_valido_lucro_real,
            is_cfop_interestadual_entrada, is_aliquota_pis_cumulativa,
            is_aliquota_cofins_cumulativa,
        )

        docs = self.sb.table("fiscal_documents").select(
            "id,tipo,chave_acesso,status,emitente_cnpj,data_emissao"
        ).eq("company_id", company_id).eq("period_id", period_id).execute().data or []

        items = self.sb.table("fiscal_items").select("*").in_(
            "document_id", [d["id"] for d in docs]
        ).execute().data if docs else []

        items_by_doc: dict[str, list] = {}
        for it in items:
            items_by_doc.setdefault(it["document_id"], []).append(it)

        # Busca CNPJ da empresa uma vez (evita N queries no loop)
        company_row = self.sb.table("fiscal_companies").select("cnpj").eq(
            "id", company_id
        ).execute().data
        my_cnpj = company_row[0]["cnpj"] if company_row else ""

        total = len(docs)
        ok = 0
        diverg = 0
        resumo: dict[str, list] = {
            "cfop_inconsistente": [],
            "cst_invalido_lucro_real": [],
            "difal_ausente": [],
            "aliquota_cumulativa": [],
            "chave_duplicada": [],
            "nota_cancelada_ativa": [],
        }

        # Verifica chaves duplicadas na consulta
        chaves = [d["chave_acesso"] for d in docs if d.get("chave_acesso")]
        chaves_duplicadas = {c for c in chaves if chaves.count(c) > 1}

        # Notas canceladas (status=cancelado mas sem verificar itens)
        canceladas_ativas = {
            d["id"] for d in docs
            if d.get("status") == "cancelado"
        }

        for doc in docs:
            doc_items = items_by_doc.get(doc["id"], [])
            divergencias_doc = []

            # Check 5: chave duplicada
            if doc.get("chave_acesso") in chaves_duplicadas:
                divergencias_doc.append("chave_acesso_duplicada")
                resumo["chave_duplicada"].append(doc["chave_acesso"])

            # Check 6: nota cancelada com lançamento ativo
            if doc["id"] in canceladas_ativas and doc.get("status") != "cancelado":
                divergencias_doc.append("nota_cancelada_lancamento_ativo")
                resumo["nota_cancelada_ativa"].append(doc.get("chave_acesso", doc["id"]))

            for item in doc_items:
                cfop = (item.get("cfop") or "").strip()
                cst_pis = (item.get("cst_pis") or "").zfill(2)
                cst_cofins = (item.get("cst_cofins") or "").zfill(2)
                aliq_pis = float(item.get("aliquota_pis") or 0)
                aliq_cofins = float(item.get("aliquota_cofins") or 0)
                difal = float(item.get("valor_icms_uf_dest") or 0)

                # Check 1: CFOP inconsistente (nota de entrada com CFOP saída ou vice-versa)
                if cfop:
                    emitente = doc.get("emitente_cnpj", "")
                    is_entrada = emitente != my_cnpj
                    if is_entrada and is_cfop_saida(cfop):
                        divergencias_doc.append(f"cfop_inconsistente:{cfop}")
                        resumo["cfop_inconsistente"].append(
                            {"doc": doc.get("chave_acesso"), "cfop": cfop}
                        )
                    elif not is_entrada and is_cfop_entrada(cfop):
                        divergencias_doc.append(f"cfop_inconsistente:{cfop}")
                        resumo["cfop_inconsistente"].append(
                            {"doc": doc.get("chave_acesso"), "cfop": cfop}
                        )

                # Check 2: CST PIS/COFINS inválido para Lucro Real
                if cst_pis and not is_cst_pis_cofins_valido_lucro_real(cst_pis):
                    divergencias_doc.append(f"cst_pis_invalido:{cst_pis}")
                    resumo["cst_invalido_lucro_real"].append(
                        {"doc": doc.get("chave_acesso"), "cst_pis": cst_pis}
                    )
                if cst_cofins and not is_cst_pis_cofins_valido_lucro_real(cst_cofins):
                    divergencias_doc.append(f"cst_cofins_invalido:{cst_cofins}")
                    resumo["cst_invalido_lucro_real"].append(
                        {"doc": doc.get("chave_acesso"), "cst_cofins": cst_cofins}
                    )

                # Check 3: DIFAL ausente em compra interestadual
                if cfop and is_cfop_interestadual_entrada(cfop) and difal == 0:
                    divergencias_doc.append(f"difal_ausente:cfop={cfop}")
                    resumo["difal_ausente"].append(
                        {"doc": doc.get("chave_acesso"), "cfop": cfop}
                    )

                # Check 4: Alíquota PIS/COFINS cumulativa
                if aliq_pis > 0 and is_aliquota_pis_cumulativa(aliq_pis):
                    divergencias_doc.append(f"aliquota_pis_cumulativa:{aliq_pis}")
                    resumo["aliquota_cumulativa"].append(
                        {"doc": doc.get("chave_acesso"), "pis": aliq_pis}
                    )
                if aliq_cofins > 0 and is_aliquota_cofins_cumulativa(aliq_cofins):
                    divergencias_doc.append(f"aliquota_cofins_cumulativa:{aliq_cofins}")
                    resumo["aliquota_cumulativa"].append(
                        {"doc": doc.get("chave_acesso"), "cofins": aliq_cofins}
                    )

            # Atualiza status do documento
            if divergencias_doc:
                diverg += 1
                self.sb.table("fiscal_documents").update({"status": "divergencia"}).eq(
                    "id", doc["id"]
                ).execute()
                # Marca itens com divergências
                for item in doc_items:
                    self.sb.table("fiscal_items").update(
                        {"divergencias": divergencias_doc}
                    ).eq("id", item["id"]).execute()
            else:
                ok += 1
                self.sb.table("fiscal_documents").update({"status": "conferido"}).eq(
                    "id", doc["id"]
                ).execute()

        _logger.info(
            "Conferência: %d docs, %d ok, %d divergências", total, ok, diverg
        )
        return {"total": total, "ok": ok, "divergencias": diverg, "resumo": resumo}
