#!/bin/sh
# Grava ~/.hermes/.env na inicialização com as env vars do container
mkdir -p /root/.hermes/logs

cat > /root/.hermes/.env << EOF
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-}
OPENAI_API_KEY=${OPENAI_API_KEY:-}
OPENAI_BASE_URL=${OPENAI_BASE_URL:-https://integrate.api.nvidia.com/v1}
GROQ_API_KEY=${GROQ_API_KEY:-}
OPENROUTER_API_KEY=${OPENROUTER_API_KEY:-}
TELEGRAM_ALLOWED_USERS=${TELEGRAM_ALLOWED_USERS:-}
EOF

# Inicia o gateway em background se alguma plataforma está habilitada no config
nohup hermes gateway run > /root/.hermes/logs/gateway.log 2>&1 &

exec uvicorn main:app --host 0.0.0.0 --port 8010
