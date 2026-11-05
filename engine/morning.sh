#!/usr/bin/env bash
# Engine run: pull current state from Supabase, score open cards, update learning, publish today's cards.
# Works identically on GitHub Actions (empty data/ dir) and in the local workspace.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/engine"
python3 run_daily.py "$@"
