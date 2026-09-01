#!/usr/bin/env bash
# Build a standalone usbversal executable with PyInstaller on this OS.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ -x .venv/bin/python ]]; then
  PYTHON=.venv/bin/python
elif [[ -x .venv/Scripts/python.exe ]]; then
  PYTHON=.venv/Scripts/python.exe
else
  echo "Run ./scripts/setup-dev.sh first (installs pyinstaller in dev extras)."
  exit 1
fi

"$PYTHON" -m pip install -e ".[dev]" -q
"$PYTHON" -m PyInstaller --noconfirm packaging/usbversal.spec

if [[ -f "$ROOT/dist/usbversal.exe" ]]; then
  ARTIFACT="$ROOT/dist/usbversal.exe"
else
  ARTIFACT="$ROOT/dist/usbversal"
fi

echo ""
echo "Built: $ARTIFACT"
echo "Smoke: $ARTIFACT  (launches the TUI)"
