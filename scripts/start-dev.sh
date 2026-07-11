#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

pip install -q -r requirements.txt 2>/dev/null || pip install -r requirements.txt

echo "==> RFID API :9000"
python3 -m api.main &
API_PID=$!

echo "==> RFID UI :5180"
cd frontend
npm install --silent 2>/dev/null || npm install
npm run dev -- --port 5180 --strictPort &
UI_PID=$!

echo ""
echo "RFID server running:"
echo "  API: http://localhost:9000"
echo "  UI:  http://localhost:5180"
echo "  Stop: kill $API_PID $UI_PID"

wait
