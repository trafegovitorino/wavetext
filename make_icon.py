#!/usr/bin/env python3
"""Gera icon_1024.png e icon.icns para o Video Transcriber."""

import subprocess
import shutil
from pathlib import Path
from PIL import Image, ImageDraw

SIZE    = 1024
RADIUS  = 220          # arredondamento do quadrado do ícone
BG      = (12, 12, 12) # quase preto
WHITE   = (255, 255, 255, 255)
SUBTLE  = (160, 160, 160, 255)


def draw_icon(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d    = ImageDraw.Draw(img)
    r    = int(RADIUS * size / SIZE)

    # Fundo arredondado
    d.rounded_rectangle([0, 0, size - 1, size - 1], radius=r, fill=BG + (255,))

    # ── Waveform ──────────────────────────────────────────────────────────────
    # 7 barras com alturas variadas; escalonadas pelo tamanho do ícone
    heights    = [0.28, 0.52, 0.76, 1.0, 0.70, 0.44, 0.24]
    n          = len(heights)
    bar_w      = int(size * 0.062)
    gap        = int(size * 0.028)
    total_w    = n * bar_w + (n - 1) * gap
    x0         = (size - total_w) // 2
    cy         = int(size * 0.44)          # centro vertical do waveform
    max_half_h = int(size * 0.22)

    for i, h in enumerate(heights):
        half_h = max(int(h * max_half_h), int(bar_w * 0.6))
        x  = x0 + i * (bar_w + gap)
        y1 = cy - half_h
        y2 = cy + half_h
        d.rounded_rectangle([x, y1, x + bar_w, y2],
                            radius=bar_w // 2, fill=WHITE)

    # ── Linhas de texto (abaixo do waveform) ──────────────────────────────────
    line_h   = int(size * 0.030)
    line_gap = int(size * 0.024)
    y_start  = cy + max_half_h + int(size * 0.10)
    widths   = [0.60, 0.46, 0.32]         # comprimentos proporcionais
    pad      = int(size * 0.18)

    for i, w_frac in enumerate(widths):
        lw = int((size - 2 * pad) * w_frac)
        y  = y_start + i * (line_h + line_gap)
        d.rounded_rectangle([pad, y, pad + lw, y + line_h],
                            radius=line_h // 2, fill=SUBTLE)

    return img


def make_icns(src_png: Path) -> Path:
    iconset = src_png.parent / "icon.iconset"
    iconset.mkdir(exist_ok=True)

    specs = [
        ("icon_16x16.png",      16),
        ("icon_16x16@2x.png",   32),
        ("icon_32x32.png",      32),
        ("icon_32x32@2x.png",   64),
        ("icon_128x128.png",   128),
        ("icon_128x128@2x.png",256),
        ("icon_256x256.png",   256),
        ("icon_256x256@2x.png",512),
        ("icon_512x512.png",   512),
        ("icon_512x512@2x.png",1024),
    ]

    master = Image.open(src_png)
    for name, sz in specs:
        resized = master.resize((sz, sz), Image.LANCZOS)
        resized.save(iconset / name)

    out = src_png.parent / "icon.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(out)],
                   check=True)
    shutil.rmtree(iconset)
    return out


if __name__ == "__main__":
    here = Path(__file__).parent

    print("Gerando icon_1024.png ...")
    img = draw_icon(SIZE)
    png_path = here / "icon_1024.png"
    img.save(png_path, "PNG")
    print(f"  Salvo: {png_path}")

    # Salva também versão menor para uso rápido na janela
    img.resize((256, 256), Image.LANCZOS).save(here / "icon_256.png", "PNG")

    print("Gerando icon.icns (para o Dock) ...")
    icns_path = make_icns(png_path)
    print(f"  Salvo: {icns_path}")

    print("\nIcone criado com sucesso.")
    print("Abra icon_1024.png para visualizar o design.")
