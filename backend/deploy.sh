#!/usr/bin/env bash
set -euo pipefail

# Caminho absoluto do projeto no servidor
APP_DIR="E:/claudecode/claudecode"

cd "$APP_DIR"

[ -f .env ] || { echo "Erro: .env nao encontrado em $APP_DIR"; exit 1; }

PREV_HEAD=$(git rev-parse HEAD)

git fetch origin main
git checkout origin/main

NEW_HEAD=$(git rev-parse HEAD)

docker compose up -d --build

echo "Deployed: ${PREV_HEAD:0:7} -> ${NEW_HEAD:0:7}"
