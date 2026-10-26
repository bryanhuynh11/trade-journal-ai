#!/bin/zsh -l
# Double-click this file (macOS) to start Trade Journal AI locally.
cd "$(dirname "$0")"
echo "== Trade Journal AI =="
if ! command -v python3 >/dev/null; then echo "python3 not found. Install Python 3 from python.org"; read; exit 1; fi
if [ ! -d .venv ]; then
  echo "First run: setting up (about 20 seconds)..."
  python3 -m venv .venv && ./.venv/bin/pip install -q -r requirements.txt || { echo "Setup failed"; read; exit 1; }
fi
if command -v claude >/dev/null; then echo "Claude Code found: $(command -v claude)"; else echo "NOTE: 'claude' not on PATH -- tick 'Mock' in the app, or install Claude Code."; fi
(sleep 2; open "http://127.0.0.1:5050") &
echo "Running at http://127.0.0.1:5050  -- close this window (or Ctrl+C) to stop."
./.venv/bin/python app.py
