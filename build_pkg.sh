#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="$SCRIPT_DIR/.venv"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  WaveText — Gerando instalador .pkg"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

cd "$SCRIPT_DIR"

# ── Recriar venv se necessário ────────────────────────────────────────────────
if [ ! -f "$VENV/bin/python3.13" ]; then
    echo "Criando ambiente virtual..."
    python3.13 -m venv "$VENV"
    "$VENV/bin/pip" install --quiet --upgrade pip
    "$VENV/bin/pip" install --quiet faster-whisper customtkinter tkinterdnd2 openai pillow pyinstaller
else
    "$VENV/bin/pip" install --quiet pyinstaller
fi

# ── Limpar builds anteriores ──────────────────────────────────────────────────
rm -rf "$SCRIPT_DIR/build" "$SCRIPT_DIR/dist" "$SCRIPT_DIR/WaveText.spec" 2>/dev/null || true

# ── Build .app com PyInstaller ────────────────────────────────────────────────
echo "Gerando WaveText.app (pode levar alguns minutos)..."

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
    --log-level WARN \
    "$SCRIPT_DIR/main.py"

APP="$SCRIPT_DIR/dist/WaveText.app"

# ── Assinar o .app ────────────────────────────────────────────────────────────
echo "Assinando o app..."
xattr -cr "$APP"
codesign --deep --force --sign - "$APP" 2>/dev/null || true

# ── Montar estrutura do instalador ────────────────────────────────────────────
echo "Criando instalador .pkg..."
PKG_ROOT="/tmp/wavetext_pkg_root"
rm -rf "$PKG_ROOT"
mkdir -p "$PKG_ROOT/Applications"
cp -r "$APP" "$PKG_ROOT/Applications/WaveText.app"

# ── Gerar o .pkg ─────────────────────────────────────────────────────────────
pkgbuild \
    --root "$PKG_ROOT" \
    --identifier "com.wavetext.app" \
    --version "1.0" \
    --install-location "/" \
    "$SCRIPT_DIR/WaveText.pkg"

rm -rf "$PKG_ROOT"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Pronto: WaveText.pkg"
echo ""
echo "  Envie este arquivo ao colega."
echo "  Ele da dois cliques e clica Instalar."
echo "  O app aparece em Aplicativos."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
