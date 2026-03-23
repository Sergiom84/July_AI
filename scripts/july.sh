#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV_PYTHON="$REPO_ROOT/.venv/bin/python"

if [ ! -f "$VENV_PYTHON" ]; then
    echo "No existe .venv. Ejecuta primero: python3 -m venv .venv && .venv/bin/pip install -e ." >&2
    exit 1
fi

exec "$VENV_PYTHON" -m july "$@"
