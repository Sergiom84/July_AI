#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
JULY_SCRIPT="$SCRIPT_DIR/july.sh"

if [ ! -f "$JULY_SCRIPT" ]; then
    echo "No existe scripts/july.sh" >&2
    exit 1
fi

exec "$JULY_SCRIPT" mcp
