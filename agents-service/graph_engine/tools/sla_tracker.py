"""
SLA Tracker — sistema de rastreamento de SLAs por agente.

Cada agente chama report_sla() ao final do seu run para registrar métricas.
O evolution_agent usa define_slas_for_agent() para criar SLAs de novos agentes.
"""
import logging
from datetime import datetime, timezone
from typing import Literal

logger = logging.getLogger(__name__)

Operator = Literal[">=", "<=", ">", "<", "="]
Unit = Literal["%", "ms", "count", "ratio", "req/min", "hours", "min"]

# SLAs pré-definidos para todos os agentes existentes
# Formato: agent_name → [(sla_name, description, target, operator, unit, warning_threshold)]
PREDEFINED_SLAS: dict[str, list[tuple]] = {
    "api_agent": [
        ("endpoint_availability_pct",   "% de endpoints respondendo 2xx/4xx",     95.0, ">=", "%",     90.0),
        ("error_5xx_detection_rate",    "% de erros 500 detectados em 24h",        90.0, ">=", "%",     75.0),
        ("check_latency_ms",            "Latência média por verificação de endpoint", 5000, "<=", "ms",  8000),
    ],
    "integration_validator": [
        ("integrations_available_pct",  "% de integrações externas disponíveis",   100.0,">=", "%",     80.0),
        ("integration_check_coverage",  "% de integrações verificadas no ciclo",   100.0,">=", "%",     90.0),
        ("error_pattern_detection_pct", "% de erros de integração identificados",   80.0,">=", "%",     60.0),
    ],
    "db_dba_agent": [
        ("bloat_tables_resolved_pct",   "% de tabelas com bloat tratadas",         100.0,">=", "%",     80.0),
        ("blocking_query_resolution_min","Tempo máx para resolver query bloqueante", 5.0,"<=", "min",   10.0),
        ("backup_success_rate",         "% de backups concluídos com sucesso",     100.0,">=", "%",     90.0),
    ],
    "security": [
        ("scan_coverage_pct",           "% do sistema coberto por verificação",    100.0,">=", "%",     90.0),
        ("critical_alert_response_min", "Tempo máx para detectar alerta crítico",   15.0,"<=", "min",   30.0),
        ("false_positive_rate",         "% de alertas que são falso positivo",      10.0,"<=", "%",     20.0),
    ],
    "code_security": [
        ("vulnerabilities_detected",    "Nº de vulnerabilidades detectadas por scan",0.0,">=", "count", 0.0),
        ("scan_completion_rate",        "% de scans concluídos sem erro",          100.0,">=", "%",     90.0),
        ("critical_vuln_response_min",  "Tempo máx para alertar vuln crítica",      30.0,"<=", "min",   60.0),
    ],
    "uptime": [
        ("services_up_pct",             "% de serviços com health OK",             100.0,">=", "%",     95.0),
        ("check_frequency_min",         "Frequência de verificação (intervalo)",    15.0,"<=", "min",   20.0),
        ("incident_detection_rate",     "% de incidentes detectados antes do usuário",90.0,">=","%",    70.0),
    ],
    "docker_intel": [
        ("containers_monitored_pct",    "% de containers cobertos pelo scan",      100.0,">=", "%",     90.0),
        ("resource_anomaly_detection",  "% de anomalias de recursos detectadas",    85.0,">=", "%",     70.0),
        ("proposal_quality_rate",       "% de proposals com descrição completa",    90.0,">=", "%",     75.0),
    ],
    "monitoring": [
        ("metrics_collected_pct",       "% de métricas coletadas sem falha",       100.0,">=", "%",     90.0),
        ("alert_latency_ms",            "Latência máx para emitir alerta",        5000.0,"<=", "ms",  10000),
        ("data_freshness_min",          "Dados com no máx X min de atraso",        15.0,"<=", "min",   30.0),
    ],
    "infrastructure": [
        ("resource_checks_pct",         "% de recursos verificados no ciclo",      100.0,">=", "%",     90.0),
        ("infra_issue_detection_rate",  "% de problemas de infra detectados",       85.0,">=", "%",     70.0),
        ("capacity_forecast_accuracy",  "% de acurácia nas previsões de capacidade",75.0,">=", "%",     60.0),
    ],
    "quality": [
        ("metrics_coverage_pct",        "% de serviços com métricas de qualidade", 100.0,">=", "%",     85.0),
        ("quality_score_avg",           "Score médio de qualidade do sistema",      70.0,">=", "%",     60.0),
        ("degradation_detection_rate",  "% de degradações detectadas antes de falha",80.0,">=","%",     65.0),
    ],
    "backend_agent": [
        ("api_error_rate",              "% de endpoints com taxa de erro < 1%",    95.0,">=", "%",     85.0),
        ("performance_regression_detected","% de regressões de performance identificadas",90.0,">=","%",75.0),
        ("proposals_generated_per_cycle","Nº de proposals de melhoria por ciclo",   1.0,">=", "count",  0.0),
    ],
    "frontend_agent": [
        ("js_error_detection_rate",     "% de erros de JS detectados",             90.0,">=", "%",     75.0),
        ("ui_health_score",             "Score de saúde do frontend",              80.0,">=", "%",     65.0),
        ("error_boundary_coverage",     "% dos erros com error boundary sugerido",  80.0,">=", "%",     60.0),
    ],
    "cicd_monitor": [
        ("pipeline_success_rate",       "% de pipelines CI/CD com sucesso",        95.0,">=", "%",     85.0),
        ("deploy_detection_latency_min","Tempo máx para detectar deploy",           5.0,"<=", "min",   10.0),
        ("failure_alert_accuracy",      "% de falhas de CI/CD alertadas",          100.0,">=", "%",     90.0),
    ],
    "log_scanner": [
        ("log_ingestion_rate",          "% de logs processados no ciclo",          100.0,">=", "%",     90.0),
        ("anomaly_detection_rate",      "% de anomalias críticas detectadas",       90.0,">=", "%",     75.0),
        ("false_positive_rate",         "% de alertas que são falso positivo",      15.0,"<=", "%",     25.0),
    ],
    "log_improver": [
        ("improvement_proposal_rate",   "% de logs ruim com proposal de melhoria",  80.0,">=", "%",     65.0),
        ("actionable_proposals_pct",    "% de proposals com ação concreta",         90.0,">=", "%",     75.0),
        ("fix_success_rate",            "% de fixes de log que melhoram qualidade", 70.0,">=", "%",     55.0),
    ],
    "evolution_agent": [
        ("proposals_generated_per_cycle","Nº de proposals estratégicas por ciclo",   2.0,">=", "count",  1.0),
        ("slas_defined_per_new_agent",  "Nº de SLAs criados para cada novo agente",  3.0,">=", "count",  3.0),
        ("briefing_delivery_rate",      "% de ciclos com briefing entregue ao CTO", 100.0,">=", "%",     90.0),
    ],
    "proposal_supervisor": [
        ("approved_execution_rate",     "% de proposals aprovadas que foram executadas",90.0,">=","%",   70.0),
        ("plan_generation_success_rate","% de proposals com plano LLM gerado",      85.0,">=", "%",     70.0),
        ("avg_execution_time_hours",    "Tempo médio para executar proposal aprovada",24.0,"<=","hours",  48.0),
    ],
    "llm_manager_agent": [
        ("provider_availability_pct",   "% de providers LLM funcionais",            80.0,">=", "%",     60.0),
        ("routing_accuracy_pct",        "% de rotas de LLM para o provider certo",  85.0,">=", "%",     70.0),
        ("avg_llm_response_time_ms",    "Latência média de resposta LLM",        30000.0,"<=", "ms",  60000),
    ],
    "opportunity_scout": [
        ("opportunities_mapped_per_cycle","Nº de oportunidades mapeadas por ciclo",  3.0,">=", "count",  1.0),
        ("signal_coverage_pct",         "% de fontes de dados verificadas",         90.0,">=", "%",     75.0),
        ("high_value_ratio",            "% de oportunidades de alta prioridade",    30.0,">=", "%",     20.0),
    ],
    "change_mgmt": [
        ("rfc_processing_rate",         "% de RFCs processadas no ciclo",          100.0,">=", "%",     90.0),
        ("sla_compliance_rate",         "% de RFCs dentro do SLA de prazo",         95.0,">=", "%",     80.0),
        ("rollback_plan_coverage",      "% de RFCs com plano de rollback",         100.0,">=", "%",     90.0),
    ],
    "automation": [
        ("automation_success_rate",     "% de automações executadas com sucesso",   95.0,">=", "%",     85.0),
        ("new_automations_per_cycle",   "Nº de novas automações identificadas",      1.0,">=", "count",  0.0),
        ("time_saved_hours",            "Horas salvas por automação no ciclo",       1.0,">=", "hours",  0.0),
    ],
    "cto_assessor_agent": [
        ("proposals_reviewed_pct",  "% de proposals aprovadas pelo CTO revisadas pelo Assessor", 100.0,">=", "%",     90.0),
        ("avg_quality_score",       "Score médio de qualidade das proposals revisadas",            7.0,">=", "count",  5.0),
        ("rejection_rate_pct",      "% de proposals rejeitadas (alerta se muito alto)",            30.0,"<=", "%",     20.0),
    ],
    "agent_health_supervisor": [
        ("agents_healthy_pct",          "% de agentes do sistema em estado OK",    100.0,">=", "%",     90.0),
        ("failing_agents_count",        "Nº de agentes em estado failing",            0.0,"<=", "count",  2.0),
        ("stale_agents_count",          "Nº de agentes com runs atrasados",           0.0,"<=", "count",  3.0),
    ],
    "scheduling": [
        ("schedule_adherence_pct",      "% de tarefas executadas no horário",       98.0,">=", "%",     90.0),
        ("delay_detection_rate",        "% de atrasos detectados proativamente",    90.0,">=", "%",     75.0),
        ("conflict_resolution_rate",    "% de conflitos de agenda resolvidos",     100.0,">=", "%",     90.0),
    ],
    "governance": [
        ("contratos_vencendo_30d",   "Contratos vigentes vencendo em 30 dias",        0.0, "<=", "count",  5.0),
        ("ocorrencias_pendentes",    "Ocorrências (glosas/multas) pendentes",          0.0, "<=", "count", 10.0),
        ("cache_age_hours",          "Horas desde último sync do cache de governança", 6.0, "<=", "hours", 12.0),
    ],
}


def define_slas_for_agent(agent_name: str, slas: list[dict]) -> int:
    """
    Cria ou atualiza SLAs para um agente.
    slas: [{"name", "description", "target", "operator", "unit", "warning_threshold", "source"}]
    Retorna número de SLAs criados/atualizados.
    """
    from db import get_supabase
    db = get_supabase()
    count = 0
    for sla in slas:
        try:
            db.table("agent_slas").upsert({
                "agent_name":         agent_name,
                "sla_name":           sla["name"],
                "description":        sla.get("description", ""),
                "target_value":       float(sla["target"]),
                "target_operator":    sla.get("operator", ">="),
                "unit":               sla.get("unit", "%"),
                "warning_threshold":  sla.get("warning_threshold"),
                "source":             sla.get("source", "evolution_agent"),
            }, on_conflict="agent_name,sla_name").execute()
            count += 1
        except Exception as exc:
            logger.warning("define_slas %s/%s: %s", agent_name, sla.get("name"), exc)
    return count


def report_sla(agent_name: str, sla_name: str, value: float) -> str:
    """
    Registra o valor atual de um SLA e recalcula o status.
    Retorna: 'ok' | 'warning' | 'critical' | 'unknown'
    """
    from db import get_supabase
    db = get_supabase()
    try:
        sla_row = (
            db.table("agent_slas")
            .select("id,target_value,target_operator,warning_threshold")
            .eq("agent_name", agent_name)
            .eq("sla_name", sla_name)
            .limit(1)
            .execute()
            .data
        )
        if not sla_row:
            return "unknown"

        row = sla_row[0]
        target = float(row["target_value"])
        op = row["target_operator"]
        warn = row.get("warning_threshold")

        # Calcula status
        ops = {">=": value >= target, "<=": value <= target, ">": value > target, "<": value < target, "=": value == target}
        meets_target = ops.get(op, False)

        if meets_target:
            status = "ok"
        elif warn is not None:
            warn_ops = {">=": value >= warn, "<=": value <= warn, ">": value > warn, "<": value < warn, "=": value == warn}
            status = "warning" if warn_ops.get(op, False) else "critical"
        else:
            status = "critical"

        now = datetime.now(timezone.utc).isoformat()
        db.table("agent_slas").update({
            "current_value": value,
            "status": status,
            "last_checked": now,
        }).eq("id", row["id"]).execute()

        db.table("agent_sla_history").insert({
            "sla_id": row["id"],
            "value": value,
            "status": status,
        }).execute()

        return status
    except Exception as exc:
        logger.warning("report_sla %s/%s: %s", agent_name, sla_name, exc)
        return "unknown"


def get_agent_sla_summary(agent_name: str) -> dict:
    """Retorna resumo dos SLAs de um agente."""
    from db import get_supabase
    db = get_supabase()
    try:
        rows = db.table("agent_slas").select("*").eq("agent_name", agent_name).execute().data or []
        ok = sum(1 for r in rows if r.get("status") == "ok")
        warn = sum(1 for r in rows if r.get("status") == "warning")
        crit = sum(1 for r in rows if r.get("status") == "critical")
        return {
            "agent": agent_name,
            "total_slas": len(rows),
            "ok": ok, "warning": warn, "critical": crit,
            "compliance_pct": round(100 * ok / max(len(rows), 1), 1),
            "slas": rows,
        }
    except Exception as exc:
        logger.warning("get_agent_sla_summary %s: %s", agent_name, exc)
        return {"agent": agent_name, "total_slas": 0, "ok": 0, "warning": 0, "critical": 0, "compliance_pct": 0}


def get_system_sla_overview() -> dict:
    """Retorna visão geral dos SLAs de todos os agentes."""
    from db import get_supabase
    db = get_supabase()
    try:
        rows = db.table("agent_slas").select("agent_name,status").execute().data or []
        by_agent: dict[str, dict] = {}
        for r in rows:
            a = r["agent_name"]
            if a not in by_agent:
                by_agent[a] = {"ok": 0, "warning": 0, "critical": 0, "unknown": 0}
            by_agent[a][r.get("status", "unknown")] = by_agent[a].get(r.get("status", "unknown"), 0) + 1

        total_slas = len(rows)
        ok_slas = sum(1 for r in rows if r.get("status") == "ok")
        return {
            "total_slas": total_slas,
            "ok": ok_slas,
            "compliance_pct": round(100 * ok_slas / max(total_slas, 1), 1),
            "agents_in_breach": [a for a, s in by_agent.items() if s.get("critical", 0) > 0],
            "by_agent": by_agent,
        }
    except Exception as exc:
        logger.warning("get_system_sla_overview: %s", exc)
        return {"total_slas": 0, "ok": 0, "compliance_pct": 0, "agents_in_breach": [], "by_agent": {}}


def seed_predefined_slas() -> int:
    """Popula o banco com todos os SLAs pré-definidos para agentes existentes."""
    total = 0
    for agent_name, slas in PREDEFINED_SLAS.items():
        sla_dicts = [
            {"name": s[0], "description": s[1], "target": s[2], "operator": s[3], "unit": s[4], "warning_threshold": s[5], "source": "system"}
            for s in slas
        ]
        total += define_slas_for_agent(agent_name, sla_dicts)
    return total
