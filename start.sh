#!/bin/bash
cd "$(dirname "$0")"
[ -f .venv/bin/python ] || (python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)
.venv/bin/python app.py
