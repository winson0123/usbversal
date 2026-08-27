#!/usr/bin/env bash
# Build standalone usbversal executable with PyInstaller (Linux).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if [[ ! -x .venv/bin/pyinstaller ]]; then
  echo "Run ./scripts/setup-dev.sh first (installs pyinstaller in dev extras)."
  exit 1
fi

.venv/bin/pip install -e ".[dev]" -q
.venv/bin/pyinstaller --noconfirm packaging/usbversal.spec

echo ""
echo "Built: $ROOT/dist/usbversal"
echo "Smoke: $ROOT/dist/usbversal  (launches the TUI)"
