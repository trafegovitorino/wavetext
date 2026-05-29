#!/usr/bin/env bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ ! -f "$VENV_DIR/bin/python" ]; then
    echo "❌  Ambiente virtual não encontrado. Execute ./install.sh primeiro."
    exit 1
fi

# Preferir python3.13 para evitar bug do python3.14 com tkinter no macOS
if [ -f "$VENV_DIR/bin/python3.13" ]; then
    "$VENV_DIR/bin/python3.13" "$SCRIPT_DIR/main.py"
else
    "$VENV_DIR/bin/python" "$SCRIPT_DIR/main.py"
fi
