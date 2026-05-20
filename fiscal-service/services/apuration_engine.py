import logging
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

_logger = logging.getLogger(__name__)

# Códigos de receita
COD_PIS    = "6912"
COD_COFINS = "5856"
COD_ICMS   = "2585"  # varia por UF, este é genérico

ALIQUOTA_PIS    = Decimal("0.0165")
ALIQUOTA_COFINS = Decimal("0.076")

# Vencimento PIS/COFINS: dia 25 do mês seguinte
# Vencimento ICMS: varia por UF, padrão dia 20


def _d(value) -> Decimal:
    try:
        return Decimal(str(value or 0))
    except Exception:
        return Decimal(0)


def _vencimento_pis_cofins(ano: int, mes: int) -> date:
    if mes == 12:
        return date(ano + 1, 1, 25)
    return date(ano, mes + 1, 25)


def _vencimento_icms(ano: int, mes: int, uf: str) -> date:
    from services.cfop_cst_tables import ICMS_VENCIMENTO_DIA
    dia = ICMS_VENCIMENTO_DIA.get(uf, 20)
    if mes == 12:
        return date(ano + 1, 1, dia)
    return date(ano, mes + 1, dia)


class ApurationEngine:
    def __init__(self, sb):
        self.sb = sb

    def run(self, company_id: str, period_id: str):
        period = self.sb.table("fiscal_periods").select("ano,mes").eq(
            "id", period_id
        ).execute().data
        if not period:
            raise ValueError("Período não encontrado")
        ano, mes = period[0]["ano"], period[0]["mes"]

        company = self.sb.table("fiscal_companies").select("uf_sede,cnpj").eq(
            "id", company_id
        ).execute().data
        uf = company[0].get("uf_sede", "SP") if company else "SP"
        my_cnpj = company[0]["cnpj"] if company else ""

        docs = self.sb.table("fiscal_documents").select(
            "id,tipo,emitente_cnpj,status"
        ).eq("company_id", company_id).eq("period_id", period_id).neq(
            "status", "cancelado"
        ).execute().data or []

        doc_ids = [d["id"] for d in docs]
        items = self.sb.table("fiscal_items").select("*").in_(
            "document_id", doc_ids
        ).execute().data if doc_ids else []

        doc_map = {d["id"]: d for d in docs}

        deb_pis = Decimal(0)
        cred_pis = Decimal(0)
        deb_cofins = Decimal(0)
        cred_cofins = Decimal(0)
        deb_icms = Decimal(0)
        cred_icms = Decimal(0)
        total_difal = Decimal(0)
        total_fcp = Decimal(0)

        det_pis = []
        det_cofins = []
        det_icms = []
        det_difal = []

        for item in items:
            doc = doc_map.get(item["document_id"])
            if not doc:
                continue

            is_saida = doc.get("emitente_cnpj") == my_cnpj

            vPIS    = _d(item.get("valor_pis"))
            vCOFINS = _d(item.get("valor_cofins"))
            vICMS   = _d(item.get("valor_icms"))
            vDIFAL  = _d(item.get("valor_icms_uf_dest"))
            vFCP    = _d(item.get("valor_fcp_uf_dest"))

            if is_saida:
                deb_pis    += vPIS
                deb_cofins += vCOFINS
                deb_icms   += vICMS
            else:
                cred_pis    += vPIS
                cred_cofins += vCOFINS
                cred_icms   += vICMS

            total_difal += vDIFAL
            total_fcp   += vFCP

        # Busca saldos credores anteriores
        prev_period = self._get_previous_saldo(period_id, "PIS")
        saldo_cred_pis = _d(prev_period)
        prev_period_cofins = self._get_previous_saldo(period_id, "COFINS")
        saldo_cred_cofins = _d(prev_period_cofins)
        prev_period_icms = self._get_previous_saldo(period_id, "ICMS")
        saldo_cred_icms = _d(prev_period_icms)

        pis_apurado    = deb_pis - cred_pis - saldo_cred_pis
        cofins_apurado = deb_cofins - cred_cofins - saldo_cred_cofins
        icms_apurado   = deb_icms - cred_icms - saldo_cred_icms

        pis_a_pagar    = max(Decimal(0), pis_apurado)
        cofins_a_pagar = max(Decimal(0), cofins_apurado)
        icms_a_pagar   = max(Decimal(0), icms_apurado)

        venc_pis_cofins = _vencimento_pis_cofins(ano, mes)
        venc_icms       = _vencimento_icms(ano, mes, uf)

        apuracoes = [
            {
                "period_id": period_id,
                "tipo_tributo": "PIS",
                "debitos": float(deb_pis.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "creditos": float(cred_pis.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "saldo_anterior": float(saldo_cred_pis.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "valor_apurado": float(pis_apurado.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "valor_a_pagar": float(pis_a_pagar.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "codigo_receita": COD_PIS,
                "data_vencimento": venc_pis_cofins.isoformat(),
                "status": "apurado",
                "detalhamento": {"aliquota": "1,65%", "regime": "nao_cumulativo"},
            },
            {
                "period_id": period_id,
                "tipo_tributo": "COFINS",
                "debitos": float(deb_cofins.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "creditos": float(cred_cofins.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "saldo_anterior": float(saldo_cred_cofins.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "valor_apurado": float(cofins_apurado.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "valor_a_pagar": float(cofins_a_pagar.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "codigo_receita": COD_COFINS,
                "data_vencimento": venc_pis_cofins.isoformat(),
                "status": "apurado",
                "detalhamento": {"aliquota": "7,6%", "regime": "nao_cumulativo"},
            },
            {
                "period_id": period_id,
                "tipo_tributo": "ICMS",
                "debitos": float(deb_icms.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "creditos": float(cred_icms.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "saldo_anterior": float(saldo_cred_icms.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "valor_apurado": float(icms_apurado.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "valor_a_pagar": float(icms_a_pagar.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "codigo_receita": COD_ICMS,
                "data_vencimento": venc_icms.isoformat(),
                "status": "apurado",
                "detalhamento": {"uf_sede": uf, "vencimento_dia": venc_icms.day},
            },
        ]

        if total_difal > 0:
            apuracoes.append({
                "period_id": period_id,
                "tipo_tributo": "DIFAL",
                "debitos": float(total_difal.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "creditos": 0,
                "saldo_anterior": 0,
                "valor_apurado": float(total_difal.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "valor_a_pagar": float(total_difal.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "codigo_receita": "2585",
                "data_vencimento": venc_icms.isoformat(),
                "status": "apurado",
                "detalhamento": {"base": "vICMSUFDest dos XMLs (EC 87/2015)"},
            })

        if total_fcp > 0:
            apuracoes.append({
                "period_id": period_id,
                "tipo_tributo": "FCP",
                "debitos": float(total_fcp.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "creditos": 0,
                "saldo_anterior": 0,
                "valor_apurado": float(total_fcp.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "valor_a_pagar": float(total_fcp.quantize(Decimal("0.01"), ROUND_HALF_UP)),
                "codigo_receita": "2585",
                "data_vencimento": venc_icms.isoformat(),
                "status": "apurado",
                "detalhamento": {"base": "vFCPUFDest dos XMLs"},
            })

        # Upsert apurações
        for ap in apuracoes:
            self.sb.table("fiscal_apurations").upsert(
                ap, on_conflict="period_id,tipo_tributo"
            ).execute()

        _logger.info(
            "Apuração período %s: PIS R$%.2f, COFINS R$%.2f, ICMS R$%.2f, DIFAL R$%.2f",
            period_id, pis_a_pagar, cofins_a_pagar, icms_a_pagar, total_difal,
        )
        return apuracoes

    def _get_previous_saldo(self, period_id: str, tipo_tributo: str) -> float:
        result = self.sb.table("fiscal_apurations").select(
            "valor_apurado"
        ).eq("period_id", period_id).eq("tipo_tributo", tipo_tributo).execute()
        # Saldo credor = valor_apurado negativo do período anterior
        if result.data:
            val = result.data[0].get("valor_apurado", 0) or 0
            return max(0, -float(val))
        return 0
