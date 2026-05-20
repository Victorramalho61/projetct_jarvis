import logging

_logger = logging.getLogger(__name__)


async def analyze_conference(report: dict) -> str:
    from db import get_settings
    settings = get_settings()
    if not settings.anthropic_api_key:
        return ""

    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

        resumo = report.get("resumo", {})
        total = report.get("total", 0)
        diverg = report.get("divergencias", 0)

        prompt = f"""Analise o resultado da conferência fiscal e forneça um resumo executivo em português:

Total de documentos conferidos: {total}
Documentos com divergências: {diverg}
Documentos OK: {report.get('ok', 0)}

Divergências encontradas:
- CFOP inconsistente: {len(resumo.get('cfop_inconsistente', []))} ocorrência(s)
- CST inválido para Lucro Real: {len(resumo.get('cst_invalido_lucro_real', []))} ocorrência(s)
- DIFAL ausente em compra interestadual: {len(resumo.get('difal_ausente', []))} ocorrência(s)
- Alíquota PIS/COFINS cumulativa (incorreta para Lucro Real): {len(resumo.get('aliquota_cumulativa', []))} ocorrência(s)
- Chaves de acesso duplicadas: {len(resumo.get('chave_duplicada', []))} ocorrência(s)
- Notas canceladas com lançamento ativo: {len(resumo.get('nota_cancelada_ativa', []))} ocorrência(s)

Forneça:
1. Resumo do status da conferência (2-3 frases)
2. Prioridade de correção (quais divergências corrigir primeiro e por quê)
3. Riscos fiscais identificados
4. Recomendações práticas para o próximo fechamento

Seja direto e objetivo. Use linguagem técnica fiscal adequada."""

        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text if msg.content else ""
    except Exception as e:
        _logger.warning("Claude analyzer falhou: %s", e)
        return ""
