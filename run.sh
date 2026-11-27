#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [[ ! -x "$VENV_PYTHON" ]]; then
    echo "Nie znaleziono środowiska projektu: $SCRIPT_DIR/.venv" >&2
    echo "Utwórz je i zainstaluj zależności poleceniami:" >&2
    echo "  cd \"$SCRIPT_DIR\"" >&2
    echo "  python3 -m venv .venv" >&2
    echo "  .venv/bin/python -m pip install -r requirements.txt" >&2
    exit 1
fi

cd "$SCRIPT_DIR"
exec "$VENV_PYTHON" "$SCRIPT_DIR/app.py" "$@"
