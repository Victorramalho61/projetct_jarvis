"""SLA Scheduler — mantido como stub após simplificação do módulo de desempenho.

O modelo de fases (goal_signing, self_assessment, etc.) foi removido.
Lembretes de pendências são agora responsabilidade do RH via painel Ciclo.
"""
import logging

_logger = logging.getLogger(__name__)


def start() -> None:
    _logger.info("SLA scheduler desativado (fases removidas no redesign do módulo)")


def stop() -> None:
    pass
