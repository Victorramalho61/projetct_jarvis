"""
Code Generator — capacidade compartilhada de geração de código e planos de implementação.

Todos os agentes podem chamar generate_implementation_plan() para obter:
- Código Python, SQL, Dockerfile, TypeScript ou comandos shell
- Estratégia de rollback
- Passos de verificação

O LLM é consultado com contexto do sistema. Se o LLM principal falhar,
tenta providers alternativos em cascata.
"""
import json
import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)

CodeType = Literal["python", "sql", "shell", "typescript", "docker", "mixed"]


def _extract_code_blocks(text: str) -> list[dict]:
    """Extrai blocos de código markdown do texto."""
    pattern = r"```(\w+)?\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    blocks = []
    for lang, code in matches:
        blocks.append({"language": lang.lower() if lang else "text", "code": code.strip()})
    return blocks


def generate_implementation_plan(
    proposal_title: str,
    proposal_description: str,
    proposal_type: str,
    proposed_action: str = "",
    proposed_fix: str = "",
    context: dict | None = None,
    timeout_s: int = 60,
) -> dict:
    """
    Gera um plano de implementação detalhado com código para uma proposal.

    Retorna:
    {
        "plan_summary": str,
        "code_blocks": [{"language": str, "code": str}],
        "implementation_steps": [str],
        "verification_steps": [str],
        "rollback_plan": str,
        "risk_assessment": str,
        "estimated_minutes": int,
        "can_auto_execute": bool,
        "auto_execute_sql": str | None,   # SQL seguro para execução automática
    }
    """
    try:
        from graph_engine.llm import get_reasoning_llm, invoke_llm_with_timeout
        from langchain_core.messages import SystemMessage, HumanMessage

        system_prompt = (
            "Você é um engenheiro de sistemas sênior full-stack com expertise em:\n"
            "- Python (FastAPI, SQLAlchemy, asyncio)\n"
            "- PostgreSQL (otimização, índices, vacuum, migrações)\n"
            "- Docker e docker-compose\n"
            "- TypeScript/React\n"
            "- Segurança e boas práticas DevOps\n\n"
            "Dado uma proposal de melhoria, gere um plano de implementação CONCRETO e EXECUTÁVEL.\n"
            "Inclua:\n"
            "1. Código real e funcional (não pseudocódigo)\n"
            "2. Passos de implementação numerados\n"
            "3. Passos de verificação (como confirmar que funcionou)\n"
            "4. Plano de rollback (como reverter se der errado)\n"
            "5. Se for SQL ANALYZE, CREATE INDEX CONCURRENTLY, VACUUM ANALYZE: marque como auto_executable=true\n\n"
            "Responda em JSON:\n"
            '{"plan_summary": str, "implementation_steps": [str], '
            '"verification_steps": [str], "rollback_plan": str, '
            '"risk_assessment": str, "estimated_minutes": int, '
            '"can_auto_execute": bool, "auto_execute_sql": str|null, '
            '"code": [{"language": "python|sql|shell|typescript|docker", "code": str}]}'
        )

        context_str = json.dumps(context or {}, ensure_ascii=False, default=str)[:500]
        user_msg = (
            f"Proposal: {proposal_title}\n"
            f"Tipo: {proposal_type}\n"
            f"Descrição: {proposal_description}\n"
            f"Ação proposta: {proposed_action}\n"
            f"Fix sugerido: {proposed_fix}\n"
            f"Contexto: {context_str}"
        )

        llm = get_reasoning_llm()
        response = invoke_llm_with_timeout(llm, [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_msg),
        ], timeout_s=timeout_s)

        content = response.content

        # Tenta parsear JSON diretamente
        try:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                data = json.loads(match.group())
                code_blocks = data.get("code", [])
                return {
                    "plan_summary": data.get("plan_summary", ""),
                    "code_blocks": code_blocks,
                    "implementation_steps": data.get("implementation_steps", []),
                    "verification_steps": data.get("verification_steps", []),
                    "rollback_plan": data.get("rollback_plan", ""),
                    "risk_assessment": data.get("risk_assessment", ""),
                    "estimated_minutes": data.get("estimated_minutes", 30),
                    "can_auto_execute": data.get("can_auto_execute", False),
                    "auto_execute_sql": data.get("auto_execute_sql"),
                }
        except json.JSONDecodeError:
            pass

        # Fallback: extrai código markdown e retorna estrutura básica
        code_blocks = _extract_code_blocks(content)
        return {
            "plan_summary": content[:500],
            "code_blocks": code_blocks,
            "implementation_steps": ["Ver plano gerado pelo LLM"],
            "verification_steps": ["Verificar manualmente após implementação"],
            "rollback_plan": "Reverter mudanças manualmente",
            "risk_assessment": "Avaliar antes de aplicar",
            "estimated_minutes": 30,
            "can_auto_execute": False,
            "auto_execute_sql": None,
        }

    except Exception as exc:
        logger.error("generate_implementation_plan: %s", exc)
        return {
            "plan_summary": f"Falha ao gerar plano: {exc}",
            "code_blocks": [],
            "implementation_steps": [],
            "verification_steps": [],
            "rollback_plan": "",
            "risk_assessment": "Indeterminado",
            "estimated_minutes": 0,
            "can_auto_execute": False,
            "auto_execute_sql": None,
        }


def save_plan_to_proposal(proposal_id: str, plan: dict) -> bool:
    """Salva o plano gerado de volta na proposal como proposed_fix."""
    try:
        from db import get_supabase
        db = get_supabase()
        plan_text = (
            f"## Plano de Implementação\n\n"
            f"{plan.get('plan_summary', '')}\n\n"
            f"### Passos\n"
            + "\n".join(f"{i+1}. {s}" for i, s in enumerate(plan.get("implementation_steps", [])))
            + "\n\n### Verificação\n"
            + "\n".join(f"- {s}" for s in plan.get("verification_steps", []))
            + f"\n\n### Rollback\n{plan.get('rollback_plan', '')}\n\n"
            + "\n\n".join(
                f"```{b['language']}\n{b['code']}\n```"
                for b in plan.get("code_blocks", [])
            )
        )
        db.table("improvement_proposals").update({
            "proposed_fix": plan_text[:5000],
        }).eq("id", proposal_id).execute()
        return True
    except Exception as exc:
        logger.error("save_plan_to_proposal %s: %s", proposal_id, exc)
        return False
