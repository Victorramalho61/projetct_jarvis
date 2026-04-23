#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${HOME}/app"

cd "$APP_DIR"

PREV_HEAD=$(git rev-parse HEAD)

git fetch origin main
git checkout origin/main

NEW_HEAD=$(git rev-parse HEAD)

source venv/bin/activate
pip install -r backend/requirements.txt

if ! systemctl restart backend; then
    echo "Restart failed — rolling back to ${PREV_HEAD:0:7}"
    git checkout "$PREV_HEAD"
    pip install -r backend/requirements.txt
    systemctl restart backend
    exit 1
fi

echo "Deployed: ${PREV_HEAD:0:7} -> ${NEW_HEAD:0:7}"
