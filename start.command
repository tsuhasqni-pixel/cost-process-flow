#!/bin/bash
APP_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$APP_DIR"
APP_URL="http://127.0.0.1:7864"
export PYTHONIOENCODING=utf-8
if [ ! -f ".venv/bin/python" ]; then
  python3 -m venv .venv && source .venv/bin/activate && python -m pip install --upgrade pip && pip install -r requirements.txt
else
  source .venv/bin/activate
fi
python -c "import flask" 2>/dev/null || pip install -r requirements.txt
(sleep 4 && open "$APP_URL") &
python -u app.py
read -p "Press Enter to close."
