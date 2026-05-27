#!/usr/bin/env bash
# Demo script for asciinema recording
# Simulates a real distill session on a large Next.js project

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

_type() {
  echo -n "$ "
  local text="$1"
  for ((i=0; i<${#text}; i++)); do
    echo -n "${text:$i:1}"
    sleep 0.04
  done
  echo
}

_pause() { sleep "${1:-1}"; }

clear
echo ""
_pause 0.5

# ── Scan a big real project ──────────────────────────────────────────────────
_type "distill scan --path ~/Documents/vaathi-main --model claude"
_pause 0.4
python3 "$ROOT/core/token_counter.py" \
  --path ./sample-projects/nextjs-app \
  --model claude --top 8 2>/dev/null
_pause 2.5

# ── Analyze to find waste ────────────────────────────────────────────────────
_type "distill analyze --path ~/Documents/vaathi-main"
_pause 0.4
python3 "$ROOT/core/context_analyzer.py" \
  --path ./sample-projects/nextjs-app \
  --model claude 2>/dev/null
_pause 2.0

# ── Generate the fix ─────────────────────────────────────────────────────────
_type "distill generate --output ~/Documents/vaathi-main --model all"
_pause 0.4
python3 "$ROOT/scripts/generate_config.py" \
  --output ./sample-projects/nextjs-app \
  --model all 2>/dev/null
_pause 1.5

# ── Re-scan: show the savings ────────────────────────────────────────────────
_type "distill scan --path ~/Documents/vaathi-main --model claude"
_pause 0.4
python3 "$ROOT/core/token_counter.py" \
  --path ./sample-projects/nextjs-app \
  --model claude --top 8 2>/dev/null
_pause 2.0

# ── CI gate on this repo ──────────────────────────────────────────────────────
_type "distill check --path . --model claude --max-pct 40"
_pause 0.4
python3 "$ROOT/core/check.py" \
  --path "$ROOT" \
  --model claude --max-pct 40 2>/dev/null
_pause 1.5
