#!/usr/bin/env bash
set -euo pipefail

# Caminho absoluto do projeto no servidor
APP_DIR="E:/claudecode/claudecode"

cd "$APP_DIR"

[ -f .env ] || { echo "Erro: .env nao encontrado em $APP_DIR"; exit 1; }

# ── Hook: auto-commit docs pendentes antes de atualizar ──────────────────
# Se houver mudanças não commitadas em docs/ (ex: arquitetura.md editado
# pelo Claude do servidor), commita e envia ao GitHub antes do checkout.
if ! git diff --quiet docs/ 2>/dev/null || git ls-files --others --exclude-standard docs/ | grep -q .; then
    echo ">>> Docs alterados — commitando antes do deploy..."
    git add docs/
    git commit -m "docs: auto-update pre-deploy $(date +%Y-%m-%d) [skip ci]"
    git push origin HEAD:main
    echo ">>> Docs enviados ao GitHub."
fi

PREV_HEAD=$(git rev-parse HEAD)

git fetch origin main
git reset --hard origin/main

NEW_HEAD=$(git rev-parse HEAD)

echo "Deployed: ${PREV_HEAD:0:7} -> ${NEW_HEAD:0:7}"

# ── Restart seletivo: só reconstrói os serviços cujos diretórios mudaram ──
# Evita derrubar a stack inteira (Kong, Supabase, todos os microsserviços)
# quando o commit só toca um serviço. Diretório de build == nome do serviço
# no docker-compose.yml para todos os itens abaixo.
KNOWN_SERVICES=(frontend core-service monitoring-service freshservice-service
                moneypenny-service agents-service expenses-service performance-service
                fiscal-service financeiro-service hermes-service cards-service
                experiencia-service support-service monitor-agent)

CHANGED_FILES=$(git diff --name-only "$PREV_HEAD" "$NEW_HEAD" 2>/dev/null || echo "")

SERVICES_TO_REBUILD=()
for svc in "${KNOWN_SERVICES[@]}"; do
    if echo "$CHANGED_FILES" | grep -q "^${svc}/"; then
        SERVICES_TO_REBUILD+=("$svc")
    fi
done

# Mudança fora de qualquer diretório de serviço conhecido (docker-compose.yml,
# volumes/, scripts/, etc.) — não dá pra saber com segurança o que foi afetado,
# reinicia tudo. docs/ é ignorado (não afeta containers).
PATTERN=$(IFS='|'; echo "${KNOWN_SERVICES[*]}")
OUTSIDE_KNOWN=$(echo "$CHANGED_FILES" | grep -vE "^(${PATTERN})/" | grep -vE "^(docs/|README)" || true)

if [ -n "$OUTSIDE_KNOWN" ] || [ ${#SERVICES_TO_REBUILD[@]} -eq 0 ]; then
    echo ">>> Mudança fora de serviços conhecidos (ou nenhum serviço alterado) — reiniciando a stack inteira"
    echo "    Nota: volumes/api/kong.yml está no .gitignore — mudanças lá exigem 'docker compose restart kong' manual, não são detectadas aqui."
    docker compose up -d --build
else
    echo ">>> Reiniciando apenas: ${SERVICES_TO_REBUILD[*]}"
    docker compose up -d --build --no-deps "${SERVICES_TO_REBUILD[@]}"
fi

echo ">>> Aguardando containers (15s)..."
sleep 15
FAILED=()
for svc in core-service monitoring-service freshservice-service \
           moneypenny-service expenses-service support-service performance-service; do
    if docker compose ps "$svc" 2>/dev/null | grep -qE "Up|healthy|running"; then
        echo "✓ $svc"
    else
        echo "✗ $svc"
        FAILED+=("$svc")
    fi
done
if [ ${#FAILED[@]} -gt 0 ]; then
    echo "AVISO: Serviços com problema: ${FAILED[*]}"
    docker compose logs --tail=30 "${FAILED[@]}"
fi

# ── Hook: dispara agente docs-sync no Jarvis ─────────────────────────────
# Usa docker exec para gerar JWT dentro do container e chamar o endpoint.
# Requer: GITHUB_TOKEN no .env + "GITHUB_TOKEN" em _SAFE_ENV_KEYS no
# agents-service/services/agent_runner.py (adicionar via dev Claude).
AGENT_ID="ef30c49e-ac5b-4ad8-a95a-252242a855c8"
echo ">>> Disparando agente docs-sync..."
docker exec jarvis-agents-service-1 python3 -c "
import jwt, httpx, os
secret = os.environ.get('JWT_SECRET', '')
token = jwt.encode({'id': 'deploy', 'role': 'admin', 'active': True}, secret, algorithm='HS256')
r = httpx.post(
    'http://localhost:8005/api/agents/$AGENT_ID/run',
    headers={'Authorization': f'Bearer {token}'},
    timeout=10,
)
print('docs-sync:', r.status_code)
" 2>&1 || echo "Aviso: trigger docs-sync falhou (nao critico)"
