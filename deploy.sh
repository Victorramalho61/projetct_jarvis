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

docker compose up -d --build

echo "Deployed: ${PREV_HEAD:0:7} -> ${NEW_HEAD:0:7}"

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
