#!/usr/bin/env bash
# Development setup for Usbversal (Python).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! python3 -m venv .venv 2>/dev/null; then
  echo "python3-venv required: sudo apt install python3-venv"
  exit 1
fi

.venv/bin/pip install -e ".[dev]"
echo "Done. Activate: source .venv/bin/activate"
