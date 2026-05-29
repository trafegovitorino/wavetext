#!/usr/bin/env bash
set -e

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  WaveText — Instalação"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

# ── Verificar Python ─────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "❌  Python 3 não encontrado."
    echo "    Instale em: https://www.python.org/downloads/"
    exit 1
fi

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
PY_MINOR=$(python3 -c "import sys; print(sys.version_info.minor)")

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 9 ]; }; then
    echo "❌  Python $PY_VER encontrado, mas é necessário Python 3.9+."
    exit 1
fi

echo "✅  Python $PY_VER encontrado."

# ── Verificar ffmpeg ─────────────────────────────────────────────────────────
if command -v ffmpeg &>/dev/null && command -v ffprobe &>/dev/null; then
    echo "✅  ffmpeg encontrado."
else
    echo ""
    echo "⚠️   ffmpeg não encontrado."
    echo "    O app funciona sem ele, mas a barra de progresso não mostrará"
    echo "    a porcentagem exata."
    echo ""
    echo "    Para instalar via Homebrew:"
    echo "      brew install ffmpeg"
    echo ""
fi

# ── Selecionar Python compatível (3.9–3.13; 3.14 tem bug com ensurepip) ─────
PY_BIN=""
for candidate in python3.13 python3.12 python3.11 python3.10 python3.9; do
    if command -v "$candidate" &>/dev/null; then
        PY_BIN=$(command -v "$candidate")
        break
    fi
done

if [ -z "$PY_BIN" ]; then
    # Fallback para python3 padrão
    PY_BIN="python3"
fi

# ── Criar ambiente virtual ───────────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "📦  Criando ambiente virtual com $PY_BIN…"
    "$PY_BIN" -m venv "$VENV_DIR"
fi

echo "📦  Instalando dependências…"
"$VENV_DIR/bin/pip" install --quiet --upgrade pip
"$VENV_DIR/bin/pip" install --quiet -r "$SCRIPT_DIR/requirements.txt"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✅  Instalação concluída!"
echo ""
echo "  Para iniciar o app, execute:"
echo "    ./run.sh"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
