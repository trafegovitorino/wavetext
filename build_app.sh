#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Gerando WaveText.app"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$SCRIPT_DIR"

# Remove build anterior
rm -rf build dist WaveText.spec 2>/dev/null || true

"$VENV/bin/python3.13" -m PyInstaller \
  --name "WaveText" \
  --windowed \
  --icon "$SCRIPT_DIR/icon.icns" \
  --add-data "$SCRIPT_DIR/icon_256.png:." \
  --add-data "$SCRIPT_DIR/icon.icns:." \
  --collect-all "tkinterdnd2" \
  --collect-all "customtkinter" \
  --collect-all "faster_whisper" \
  --collect-all "ctranslate2" \
  --hidden-import "PIL" \
  --hidden-import "PIL.ImageTk" \
  --hidden-import "openai" \
  --noconfirm \
  "$SCRIPT_DIR/main.py"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pronto!  dist/WaveText.app"
echo ""
echo "  Para compartilhar:"
echo "  1. Arraste o .app para o Finder"
echo "  2. Clique direito → Comprimir"
echo "  3. Envie o .zip para o colega"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
