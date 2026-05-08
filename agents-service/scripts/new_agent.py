"""
CLI para criação de novos agentes a partir do template padrão.

Uso:
  python scripts/new_agent.py <nome_do_agente> <pipeline>

Exemplo:
  python scripts/new_agent.py invoice_checker governance

Pipelines disponíveis: governance, security, monitoring, cicd, dba, evolution, documentation, manual
"""
import re
import sys
import os

_AGENTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "graph_engine", "agents")
_RUNNER_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "services", "agent_runner.py")
_TEMPLATE_PATH = os.path.join(_AGENTS_DIR, "_template.py")

_VALID_PIPELINES = {
    "governance", "security", "monitoring", "cicd",
    "dba", "evolution", "documentation", "manual",
}


def _snake(name: str) -> str:
    return re.sub(r"[^a-z0-9_]", "_", name.lower().strip())


def create_agent(name: str, pipeline: str) -> None:
    name = _snake(name)
    if not name:
        print("ERRO: nome inválido")
        sys.exit(1)
    if pipeline not in _VALID_PIPELINES:
        print(f"ERRO: pipeline '{pipeline}' inválido. Opções: {', '.join(sorted(_VALID_PIPELINES))}")
        sys.exit(1)

    agent_path = os.path.join(_AGENTS_DIR, f"{name}.py")
    if os.path.exists(agent_path):
        print(f"ERRO: {agent_path} já existe")
        sys.exit(1)

    # Criar arquivo de agente a partir do template
    with open(_TEMPLATE_PATH) as f:
        content = f.read()
    content = content.replace("<AGENT_NAME>", name)
    content = content.replace(
        "<governance|security|monitoring|cicd|dba|evolution|documentation>",
        pipeline,
    )
    with open(agent_path, "w") as f:
        f.write(content)
    print(f"[ok] Criado: {agent_path}")

    # Registrar no _PIPELINE_AGENTS do agent_runner.py
    with open(_RUNNER_PATH) as f:
        runner = f.read()

    marker = f'"{pipeline}":  ['
    if marker not in runner:
        marker = f'"{pipeline}": ['
    if marker not in runner:
        print(f"[warn] Pipeline '{pipeline}' não encontrado em agent_runner.py — adicione manualmente")
        print(f"       Adicione '{name}' à lista do pipeline '{pipeline}' em _PIPELINE_AGENTS")
        return

    # Insere antes do fechamento da lista do pipeline
    # Encontra a posição após o marcador e antes do "],"
    idx = runner.index(marker)
    close_idx = runner.index("],", idx)
    last_quote_idx = runner.rindex('"', idx, close_idx)
    insert_pos = last_quote_idx + 1
    new_runner = runner[:insert_pos] + f',\n        "{name}"' + runner[insert_pos:]

    with open(_RUNNER_PATH, "w") as f:
        f.write(new_runner)
    print(f"[ok] '{name}' registrado no pipeline '{pipeline}' em agent_runner.py")
    print(f"\nPróximos passos:")
    print(f"  1. Edite {agent_path} e implemente a função run()")
    print(f"  2. Atualize a docstring SLA com tipo, timeout e findings esperados")
    print(f"  3. Faça rebuild do container: docker compose up -d --build agents-service")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    create_agent(sys.argv[1], sys.argv[2])
