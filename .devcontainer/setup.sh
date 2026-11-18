#!/usr/bin/env bash
# Roda uma vez quando o Codespace e criado
set -e
pip install -r backend/requirements.txt pytest
[ -f backend/.env ] || cp backend/.env.example backend/.env
cd app && npm install && npm run build
echo "Pronto. Para abrir o painel: cd backend && python app.py"
