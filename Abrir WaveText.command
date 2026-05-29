#!/bin/bash
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR"

echo ""
echo "  WaveText — configurando..."
echo ""

# ── Encontrar Python 3.9+ ──────────────────────────────────────────────────────
PYTHON=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3.9 python3; do
    if command -v "$candidate" &>/dev/null; then
        MAJ=$("$candidate" -c "import sys; print(sys.version_info.major)" 2>/dev/null)
        MIN=$("$candidate" -c "import sys; print(sys.version_info.minor)" 2>/dev/null)
        if [ "$MAJ" = "3" ] && [ "$MIN" -ge 9 ] 2>/dev/null; then
            PYTHON=$(command -v "$candidate")
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "  Python nao encontrado."
    echo "  Abrindo python.org para download..."
    open "https://www.python.org/downloads/"
    echo ""
    echo "  Instale o Python e abra este arquivo novamente."
    echo ""
    read -p "  Pressione Enter para fechar..."
    exit 1
fi

echo "  Python encontrado: $PYTHON"

# ── Criar ambiente virtual se necessário ──────────────────────────────────────
if [ ! -f ".venv/bin/python" ]; then
    echo "  Instalando dependencias (so na primeira vez)..."
    "$PYTHON" -m venv .venv
    .venv/bin/pip install --quiet --upgrade pip
    .venv/bin/pip install --quiet faster-whisper customtkinter tkinterdnd2 openai pillow
    echo "  Instalacao concluida."
fi

# ── Abrir o app ───────────────────────────────────────────────────────────────
echo "  Abrindo WaveText..."
.venv/bin/python main.py &

sleep 3
# Fecha o Terminal automaticamente
osascript -e 'tell application "Terminal" to close (every window whose name contains "command")' 2>/dev/null || true
