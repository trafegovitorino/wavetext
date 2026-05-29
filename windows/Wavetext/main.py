#!/usr/bin/env python3
"""WaveText — transcrição local (Whisper) ou via OpenAI API"""

import json
import os
import queue
import re
import subprocess
import tempfile
import threading
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk
from tkinterdnd2 import DND_FILES, TkinterDnD

# ─── Tema ──────────────────────────────────────────────────────────────────────

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

BG        = "#FFFFFF"
SURFACE   = "#F7F7F8"
BORDER    = "#E5E5E5"
TEXT      = "#0A0A0A"
MUTED     = "#6B7280"
PRIMARY   = "#0A0A0A"
PRIMARY_H = "#262626"
SECONDARY = "#FFFFFF"
SEC_HOVER = "#F3F3F3"

STATUS_COLOR = {
    "pending":    "#9CA3AF",
    "processing": "#3B82F6",
    "done":       "#10A37F",
    "error":      "#EF4444",
}

# ─── Constantes ────────────────────────────────────────────────────────────────

SUPPORTED_EXT = {
    # Vídeo
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v",
    # Áudio
    ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac", ".opus", ".aiff", ".wma", ".mp2",
}
LOCAL_MODELS  = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]
OPENAI_MODELS = ["whisper-1", "gpt-4o-transcribe", "gpt-4o-mini-transcribe"]
CONFIG_PATH   = Path.home() / ".wavetext.json"


# ─── Config persistente ────────────────────────────────────────────────────────

def _load_cfg() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text())
    except Exception:
        return {}

def _save_cfg(data: dict):
    try:
        CONFIG_PATH.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


# ─── Modelo de dados ───────────────────────────────────────────────────────────

class QueueItem:
    PENDING    = "pending"
    PROCESSING = "processing"
    DONE       = "done"
    ERROR      = "error"

    def __init__(self, path: str):
        self.path      = Path(path)
        self.name      = self.path.name
        self.status    = self.PENDING
        self.progress: float = 0.0
        self.language: str   = ""
        self.error_msg: str  = ""
        self.duration: float = 0.0


# ─── Widget de item da fila ────────────────────────────────────────────────────

class QueueItemWidget(ctk.CTkFrame):
    def __init__(self, parent, item: QueueItem, on_remove, **kw):
        kw.setdefault("fg_color", BG)
        kw.setdefault("border_color", BORDER)
        kw.setdefault("border_width", 1)
        kw.setdefault("corner_radius", 8)
        super().__init__(parent, **kw)
        self.item      = item
        self.on_remove = on_remove
        self._pulsing  = False
        self._build()

    def _build(self):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(11, 6))

        self.dot = ctk.CTkLabel(row, text="●", width=14,
                                font=ctk.CTkFont(size=10),
                                text_color=STATUS_COLOR["pending"])
        self.dot.pack(side="left", padx=(0, 10))

        info = ctk.CTkFrame(row, fg_color="transparent")
        info.pack(side="left", fill="x", expand=True)

        name = self.item.name if len(self.item.name) <= 54 else self.item.name[:51] + "…"
        ctk.CTkLabel(info, text=name, font=ctk.CTkFont(size=13),
                     text_color=TEXT, anchor="w").pack(fill="x")

        self.sub = ctk.CTkLabel(info, text="Aguardando",
                                font=ctk.CTkFont(size=11),
                                text_color=MUTED, anchor="w")
        self.sub.pack(fill="x")

        ctk.CTkButton(row, text="✕", width=24, height=24,
                      font=ctk.CTkFont(size=11),
                      fg_color="transparent", text_color=MUTED,
                      hover_color=SEC_HOVER, border_width=0,
                      command=lambda: self.on_remove(self)).pack(side="right")

        self.bar = ctk.CTkProgressBar(self, height=2, corner_radius=1,
                                      fg_color=BORDER, progress_color=PRIMARY)
        self.bar.pack(fill="x", padx=14, pady=(0, 10))
        self.bar.set(0)

    def refresh(self):
        s = self.item.status
        self.dot.configure(text_color=STATUS_COLOR.get(s, MUTED))

        if s == "processing":
            lang = f"  {self.item.language.upper()}" if self.item.language else ""
            if self.item.progress <= 0:
                if not self._pulsing:
                    self._pulsing = True
                    self.bar.configure(mode="indeterminate")
                    self.bar.start()
                self.sub.configure(text=f"Analisando audio{lang}...",
                                   text_color=STATUS_COLOR["processing"])
            else:
                if self._pulsing:
                    self._pulsing = False
                    self.bar.stop()
                    self.bar.configure(mode="determinate")
                self.bar.set(self.item.progress / 100)
                self.sub.configure(
                    text=f"Transcrevendo{lang}  {self.item.progress:.0f}%",
                    text_color=STATUS_COLOR["processing"],
                )
        else:
            if self._pulsing:
                self._pulsing = False
                self.bar.stop()
                self.bar.configure(mode="determinate")
            self.bar.set(self.item.progress / 100)

            if s == "pending":
                self.sub.configure(text="Aguardando", text_color=MUTED)
            elif s == "done":
                self.sub.configure(text="Concluido", text_color=STATUS_COLOR["done"])
            elif s == "error":
                self.sub.configure(
                    text=f"Erro: {self.item.error_msg[:68]}",
                    text_color=STATUS_COLOR["error"],
                )


# ─── Zona de drag & drop ───────────────────────────────────────────────────────

class DropZone(ctk.CTkFrame):
    _BORDER_IDLE   = BORDER
    _BORDER_ACTIVE = PRIMARY

    def __init__(self, parent, on_add, **kw):
        kw.setdefault("fg_color", SURFACE)
        kw.setdefault("border_color", self._BORDER_IDLE)
        kw.setdefault("border_width", 1)
        kw.setdefault("corner_radius", 10)
        super().__init__(parent, **kw)
        self.on_add = on_add
        self._build()
        self._setup_dnd()

    def _build(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.place(relx=0.5, rely=0.5, anchor="center")

        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack()
        ctk.CTkLabel(row, text="Arraste audio ou video aqui",
                     font=ctk.CTkFont(size=13, weight="bold"),
                     text_color=TEXT).pack(side="left")
        ctk.CTkLabel(row, text="  —  MP3  WAV  AAC  FLAC  MP4  MKV e mais",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(side="left")

        ctk.CTkButton(inner, text="Selecionar arquivos",
                      height=28, width=160,
                      fg_color=SECONDARY, border_width=1, border_color=BORDER,
                      text_color=TEXT, hover_color=SEC_HOVER,
                      font=ctk.CTkFont(size=11), corner_radius=6,
                      command=self._open_dialog).pack(pady=(8, 0))

    def _setup_dnd(self):
        self.drop_target_register(DND_FILES)
        self.dnd_bind("<<Drop>>",      self._on_drop)
        self.dnd_bind("<<DragEnter>>", lambda _: self.configure(border_color=self._BORDER_ACTIVE))
        self.dnd_bind("<<DragLeave>>", lambda _: self.configure(border_color=self._BORDER_IDLE))

    def _on_drop(self, event):
        self.configure(border_color=self._BORDER_IDLE)
        paths = _parse_drop(event.data)
        if paths:
            self.on_add(paths)

    def _open_dialog(self):
        files = filedialog.askopenfilenames(
            title="Selecionar arquivos",
            filetypes=[
                ("Audio", "*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.opus *.aiff *.wma *.mp2"),
                ("Video", "*.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v"),
                ("Audio e Video", "*.mp3 *.wav *.m4a *.flac *.ogg *.aac *.opus *.aiff *.wma *.mp2 *.mp4 *.mkv *.avi *.mov *.wmv *.flv *.webm *.m4v"),
                ("Todos os arquivos", "*.*"),
            ],
        )
        if files:
            self.on_add(list(files))


# ─── Toggle de modo ───────────────────────────────────────────────────────────

class ModeToggle(ctk.CTkFrame):
    """Pill com card branco elevado para a opção ativa."""

    _PILL    = "#E8E8E8"
    _SEL_BG  = "#FFFFFF"
    _SEL_HVR = "#F8F8F8"
    _UNS_HVR = "#DCDCDC"

    def __init__(self, parent, options: list[str], default: str,
                 on_change=None, btn_width=110, **kw):
        kw.setdefault("fg_color", self._PILL)
        kw.setdefault("corner_radius", 9)
        super().__init__(parent, **kw)
        self._on_change = on_change
        self._selected  = default
        self._btns: dict[str, ctk.CTkButton] = {}
        self._fill      = (btn_width is None)

        for i, opt in enumerate(options):
            is_first = i == 0
            is_last  = i == len(options) - 1
            w = 0 if self._fill else btn_width
            btn = ctk.CTkButton(
                self, text=opt, width=w, height=34,
                corner_radius=7,
                font=ctk.CTkFont(size=12),
                command=lambda o=opt: self._pick(o),
            )
            pack_kw = dict(
                side="left",
                padx=(4 if is_first else 2, 4 if is_last else 2),
                pady=4,
            )
            if self._fill:
                pack_kw["fill"] = "x"
                pack_kw["expand"] = True
            btn.pack(**pack_kw)
            self._btns[opt] = btn

        self._render()

    def _pick(self, option: str):
        if self._selected == option:
            return
        self._selected = option
        self._render()
        if self._on_change:
            self._on_change(option)

    def _render(self):
        for opt, btn in self._btns.items():
            if opt == self._selected:
                btn.configure(
                    fg_color=self._SEL_BG,
                    hover_color=self._SEL_HVR,
                    text_color=TEXT,
                    font=ctk.CTkFont(size=12, weight="bold"),
                )
            else:
                btn.configure(
                    fg_color="transparent",
                    hover_color=self._UNS_HVR,
                    text_color=MUTED,
                    font=ctk.CTkFont(size=12),
                )

    def get(self) -> str:
        return self._selected

    def set(self, value: str):
        if value in self._btns:
            self._selected = value
            self._render()


# ─── Janela principal ──────────────────────────────────────────────────────────

class App(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("WaveText")
        self.geometry("760x800")
        self.minsize(640, 640)
        self.configure(bg=BG)
        self._apply_icon()

        self._items: list[QueueItem]         = []
        self._widgets: list[QueueItemWidget] = []
        self._work_queue: queue.Queue        = queue.Queue()
        self._model_cache: dict              = {}
        self._is_running                     = False
        self._stop_flag                      = False
        self.output_dir                      = Path.home() / "Desktop"

        self._cfg = _load_cfg()
        self._build_ui()

        threading.Thread(target=self._worker, daemon=True).start()

        # Fechar pela janela (X) ou Cmd+Q encerra o processo corretamente
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.bind("<Command-q>", lambda _: self._on_close())
        self.bind("<Command-w>", lambda _: self._on_close())

    # ── Ícone ─────────────────────────────────────────────────────────────────

    def _apply_icon(self):
        png = Path(__file__).parent / "icon_256.png"
        if not png.exists():
            return
        try:
            from PIL import Image, ImageTk
            img          = Image.open(png).resize((64, 64), Image.LANCZOS)
            photo        = ImageTk.PhotoImage(img)
            self.wm_iconphoto(True, photo)
            self._icon_ref = photo  # evita garbage collection
        except Exception:
            pass

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Cabeçalho ─────────────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, height=52, corner_radius=0, fg_color=BG)
        hdr.pack(side="top", fill="x")
        hdr.pack_propagate(False)
        ctk.CTkLabel(hdr, text="WaveText",
                     font=ctk.CTkFont(size=15, weight="bold"),
                     text_color=TEXT).pack(side="left", padx=22, pady=14)
        ctk.CTkFrame(self, height=1, corner_radius=0,
                     fg_color=BORDER).pack(side="top", fill="x")

        # ── Barra de ação (rodapé fixo) ────────────────────────────────────
        self._build_action_bar()

        # ── Corpo ─────────────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color=BG)
        body.pack(side="top", fill="both", expand=True, padx=20, pady=(14, 0))

        # 1. Configurações
        self._build_settings(body)

        # 2. Drop zone
        self.drop_zone = DropZone(body, self._add_files, height=106)
        self.drop_zone.pack(fill="x", pady=(12, 0))

        # 3. Cabeçalho + lista da fila
        self._build_queue_section(body)

    def _build_settings(self, parent):
        cfg = ctk.CTkFrame(parent, fg_color=BG,
                           border_color=BORDER, border_width=1, corner_radius=10)
        cfg.pack(fill="x")

        p = ctk.CTkFrame(cfg, fg_color="transparent")
        p.pack(fill="x", padx=18, pady=16)

        # ── Modo ──────────────────────────────────────────────────────────────
        self._mode_toggle = ModeToggle(
            p, options=["Local", "OpenAI API"],
            default=self._cfg.get("mode", "Local"),
            on_change=self._on_mode_change,
            btn_width=None,   # fill mode
        )
        self._mode_toggle.pack(fill="x")

        _hsep(p)

        # ── Painel dinâmico ────────────────────────────────────────────────────
        self._dyn_host = ctk.CTkFrame(p, fg_color="transparent")
        self._dyn_host.pack(fill="x")

        # Local: label + dropdown
        self._panel_local = ctk.CTkFrame(self._dyn_host, fg_color="transparent")
        ctk.CTkLabel(self._panel_local, text="Modelo",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w", pady=(0, 5))
        self.local_model_var = ctk.StringVar(value=self._cfg.get("local_model", "medium"))
        ctk.CTkOptionMenu(
            self._panel_local, variable=self.local_model_var,
            values=LOCAL_MODELS, width=0, height=34,
            fg_color=SURFACE, button_color=SURFACE,
            button_hover_color=SEC_HOVER,
            dropdown_fg_color=BG, dropdown_hover_color=SURFACE,
            text_color=TEXT, dropdown_text_color=TEXT,
            corner_radius=6,
            command=lambda v: self._persist("local_model", v),
        ).pack(fill="x")

        # API: key + show + modelo
        self._panel_api = ctk.CTkFrame(self._dyn_host, fg_color="transparent")

        ctk.CTkLabel(self._panel_api, text="OpenAI API Key",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w", pady=(0, 5))
        key_row = ctk.CTkFrame(self._panel_api, fg_color="transparent")
        key_row.pack(fill="x")
        self.api_key_var = ctk.StringVar(value=self._cfg.get("openai_api_key", ""))
        self._key_entry = ctk.CTkEntry(
            key_row, textvariable=self.api_key_var,
            height=34, show="●", placeholder_text="sk-...",
            fg_color=SURFACE, border_color=BORDER,
            text_color=TEXT, placeholder_text_color=MUTED,
            corner_radius=6, font=ctk.CTkFont(size=12),
        )
        self._key_entry.pack(side="left", fill="x", expand=True)
        self._key_entry.bind(
            "<FocusOut>", lambda _: self._persist("openai_api_key", self.api_key_var.get()))
        self._show_key = False
        self._show_btn = ctk.CTkButton(
            key_row, text="Mostrar", width=72, height=34,
            fg_color=SURFACE, hover_color=SEC_HOVER,
            border_width=1, border_color=BORDER,
            text_color=MUTED, font=ctk.CTkFont(size=11),
            corner_radius=6, command=self._toggle_key_visibility,
        )
        self._show_btn.pack(side="left", padx=(6, 0))

        ctk.CTkLabel(self._panel_api, text="Modelo",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w", pady=(10, 5))
        self.openai_model_var = ctk.StringVar(
            value=self._cfg.get("openai_model", "whisper-1"))
        ctk.CTkOptionMenu(
            self._panel_api, variable=self.openai_model_var,
            values=OPENAI_MODELS, width=0, height=34,
            fg_color=SURFACE, button_color=SURFACE,
            button_hover_color=SEC_HOVER,
            dropdown_fg_color=BG, dropdown_hover_color=SURFACE,
            text_color=TEXT, dropdown_text_color=TEXT,
            corner_radius=6,
            command=lambda v: self._persist("openai_model", v),
        ).pack(fill="x")

        self._show_mode_panel()

        _hsep(p)

        # ── Formato de saída ───────────────────────────────────────────────────
        ctk.CTkLabel(p, text="Formato de saida",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w", pady=(0, 5))
        fmts = ctk.CTkFrame(p, fg_color="transparent")
        fmts.pack(fill="x")
        self.want_txt = ctk.BooleanVar(value=True)
        self.want_srt = ctk.BooleanVar(value=True)
        for label, var in [("TXT", self.want_txt), ("SRT", self.want_srt)]:
            ctk.CTkCheckBox(fmts, text=label, variable=var,
                            height=34, checkbox_width=16, checkbox_height=16,
                            border_color=BORDER, checkmark_color=BG,
                            fg_color=PRIMARY, hover_color=PRIMARY_H,
                            text_color=TEXT,
                            font=ctk.CTkFont(size=13)).pack(side="left", padx=(0, 16))

        _hsep(p)

        # ── Pasta de saída ─────────────────────────────────────────────────────
        ctk.CTkLabel(p, text="Pasta de saida",
                     font=ctk.CTkFont(size=11), text_color=MUTED).pack(anchor="w", pady=(0, 5))
        out_row = ctk.CTkFrame(p,
                               fg_color=SURFACE, border_color=BORDER,
                               border_width=1, corner_radius=6)
        out_row.pack(fill="x")
        self.out_lbl = ctk.CTkLabel(
            out_row, text=_shorten(self.output_dir, n=52),
            font=ctk.CTkFont(size=12), text_color=MUTED, anchor="w",
        )
        self.out_lbl.pack(side="left", fill="x", expand=True, padx=12, pady=9)
        ctk.CTkButton(
            out_row, text="Alterar", width=80, height=34,
            fg_color=BG, hover_color=SEC_HOVER,
            border_width=1, border_color=BORDER,
            text_color=TEXT, font=ctk.CTkFont(size=12),
            corner_radius=6, command=self._pick_output,
        ).pack(side="right", padx=4, pady=4)

    def _build_queue_section(self, parent):
        hdr = ctk.CTkFrame(parent, fg_color="transparent")
        hdr.pack(fill="x", pady=(12, 4))
        ctk.CTkLabel(hdr, text="Fila de transcricao",
                     font=ctk.CTkFont(size=12, weight="bold"),
                     text_color=TEXT).pack(side="left")
        self.count_lbl = ctk.CTkLabel(hdr, text="0 itens",
                                      font=ctk.CTkFont(size=11), text_color=MUTED)
        self.count_lbl.pack(side="left", padx=8)
        ctk.CTkButton(
            hdr, text="Limpar concluidos", width=124, height=26,
            fg_color=SECONDARY, hover_color=SEC_HOVER,
            border_width=1, border_color=BORDER,
            text_color=MUTED, font=ctk.CTkFont(size=11),
            corner_radius=6, command=self._clear_done,
        ).pack(side="right")

        self.scroll = ctk.CTkScrollableFrame(
            parent, fg_color=SURFACE,
            border_color=BORDER, border_width=1, corner_radius=10,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color="#D1D5DB",
        )
        self.scroll.pack(fill="both", expand=True)

        self.empty_lbl = ctk.CTkLabel(
            self.scroll,
            text="Nenhum arquivo na fila.\nArraste audio ou video acima para comecar.",
            font=ctk.CTkFont(size=13), text_color="#C0C0C0",
        )
        self.empty_lbl.pack(expand=True, pady=36)

    def _build_action_bar(self):
        ctk.CTkFrame(self, height=1, corner_radius=0,
                     fg_color=BORDER).pack(side="bottom", fill="x")
        bar = ctk.CTkFrame(self, fg_color=BG)
        bar.pack(side="bottom", fill="x", padx=20, pady=12)

        self.status_lbl = ctk.CTkLabel(bar, text="Pronto",
                                       font=ctk.CTkFont(size=12), text_color=MUTED)
        self.status_lbl.pack(side="left")

        self.stop_btn = ctk.CTkButton(
            bar, text="Parar", width=96, height=36,
            fg_color=SECONDARY, hover_color=SEC_HOVER,
            border_width=1, border_color=BORDER,
            text_color=MUTED, font=ctk.CTkFont(size=13),
            corner_radius=6, state="disabled", command=self._stop,
        )
        self.stop_btn.pack(side="right", padx=(8, 0))

        self.start_btn = ctk.CTkButton(
            bar, text="Iniciar transcricao", width=164, height=36,
            fg_color=PRIMARY, hover_color=PRIMARY_H,
            text_color="#FFFFFF", font=ctk.CTkFont(size=13, weight="bold"),
            corner_radius=6, command=self._start,
        )
        self.start_btn.pack(side="right")

    # ── Modo ──────────────────────────────────────────────────────────────────

    def _on_mode_change(self, value: str):
        self._persist("mode", value)
        self._show_mode_panel()

    def _show_mode_panel(self):
        if self._mode_toggle.get() == "Local":
            self._panel_api.pack_forget()
            self._panel_local.pack()
        else:
            self._panel_local.pack_forget()
            self._panel_api.pack()

    def _toggle_key_visibility(self):
        self._show_key = not self._show_key
        self._key_entry.configure(show="" if self._show_key else "●")

    # ── Config ────────────────────────────────────────────────────────────────

    def _persist(self, key: str, value):
        self._cfg[key] = value
        _save_cfg(self._cfg)

    # ── Fila ──────────────────────────────────────────────────────────────────

    def _add_files(self, paths: list[str]):
        added = 0
        for p in paths:
            path = Path(p)
            if path.suffix.lower() not in SUPPORTED_EXT:
                continue
            if any(i.path == path for i in self._items):
                continue
            item = QueueItem(str(path))
            self._items.append(item)
            w = QueueItemWidget(self.scroll, item, self._remove_widget)
            w.pack(fill="x", pady=(0, 6), padx=6)
            self._widgets.append(w)
            self._animate_item_in(w)
            added += 1
        if added:
            self._sync_ui()

    def _animate_item_in(self, widget: "QueueItemWidget"):
        """Fade suave de azul claro para branco ao adicionar item."""
        frames = ["#EEF4FF", "#F4F7FF", "#F9FBFF", BG]
        def step(i=0):
            if i < len(frames):
                try:
                    widget.configure(fg_color=frames[i])
                    self.after(100, step, i + 1)
                except Exception:
                    pass
        step()

    def _remove_widget(self, widget: QueueItemWidget):
        if widget.item.status == "processing":
            return
        idx = self._widgets.index(widget)
        self._items.pop(idx)
        self._widgets.pop(idx)
        widget.destroy()
        self._sync_ui()

    def _clear_done(self):
        to_kill = [w for it, w in zip(self._items, self._widgets)
                   if it.status in ("done", "error")]
        for w in reversed(to_kill):
            idx = self._widgets.index(w)
            self._items.pop(idx)
            self._widgets.pop(idx)
            w.destroy()
        self._sync_ui()

    def _sync_ui(self):
        if self._items:
            self.empty_lbl.pack_forget()
        else:
            self.empty_lbl.pack(expand=True, pady=36)
        n = len(self._items)
        self.count_lbl.configure(text=f"{n} item{'s' if n != 1 else ''}")

    # ── Ações ─────────────────────────────────────────────────────────────────

    def _pick_output(self):
        d = filedialog.askdirectory(title="Escolher pasta de saida",
                                    initialdir=str(self.output_dir))
        if d:
            self.output_dir = Path(d)
            self.out_lbl.configure(text=_shorten(self.output_dir))

    def _start(self):
        if not self.want_txt.get() and not self.want_srt.get():
            self._set_status("Selecione pelo menos um formato de saida.")
            return
        if self._mode_toggle.get() == "OpenAI API" and not self.api_key_var.get().strip():
            self._set_status("Informe a OpenAI API Key nas configuracoes.")
            return
        pending = [it for it in self._items if it.status == "pending"]
        if not pending:
            self._set_status("Nenhum item pendente na fila.")
            return
        self._stop_flag  = False
        self._is_running = True
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal", fg_color=SURFACE, text_color=TEXT)
        for it in pending:
            self._work_queue.put(it)

    def _stop(self):
        self._stop_flag = True
        self._set_status("Parando apos o arquivo atual...")
        self.stop_btn.configure(state="disabled")

    def _on_close(self):
        self._stop_flag = True   # sinaliza worker para parar
        self.destroy()           # fecha a janela e encerra o processo
        import sys; sys.exit(0)

    # ── Worker ────────────────────────────────────────────────────────────────

    def _worker(self):
        while True:
            try:
                item = self._work_queue.get(timeout=1)
            except queue.Empty:
                if self._is_running and self._work_queue.empty():
                    self._is_running = False
                    self.after(0, self._all_done)
                continue
            if self._stop_flag:
                item.status = "pending"
                self.after(0, self._refresh, item)
                self._work_queue.task_done()
                continue
            if self._mode_toggle.get() == "OpenAI API":
                self._transcribe_openai(item)
            else:
                self._transcribe_local(item)
            self._work_queue.task_done()

    # ── Transcrição local (faster-whisper) ────────────────────────────────────

    def _transcribe_local(self, item: QueueItem):
        item.status   = "processing"
        item.progress = 0.0
        self.after(0, self._refresh, item)
        self.after(0, self._set_status, f"Analisando: {item.name}")

        try:
            from faster_whisper import WhisperModel

            model_name = self.local_model_var.get()
            if model_name not in self._model_cache:
                self.after(0, self._set_status, f"Carregando modelo {model_name}...")
                self._model_cache.clear()
                self._model_cache[model_name] = WhisperModel(
                    model_name, device="cpu",
                    compute_type="auto", cpu_threads=0,
                )
            model    = self._model_cache[model_name]
            duration = _get_duration(item.path)
            item.duration = duration

            segments_gen, info = model.transcribe(
                str(item.path), language=None,
                beam_size=3, word_timestamps=False,
            )
            item.language = info.language
            self.after(0, self._set_status,
                       f"Transcrevendo [{info.language.upper()}]: {item.name}")
            self.after(0, self._refresh, item)

            segments: list = []
            for seg in segments_gen:
                if self._stop_flag:
                    item.status    = "error"
                    item.error_msg = "Interrompido pelo usuario"
                    self.after(0, self._refresh, item)
                    return
                segments.append(seg)
                if duration > 0:
                    item.progress = min(99.0, seg.end / duration * 100)
                else:
                    item.progress = min(99.0, item.progress + 0.5)
                self.after(0, self._refresh, item)

            _write_outputs(segments, item, self.output_dir,
                           self.want_txt.get(), self.want_srt.get())
            item.status   = "done"
            item.progress = 100.0

        except Exception as exc:
            item.status    = "error"
            item.error_msg = str(exc)
            item.progress  = 0.0

        self.after(0, self._refresh, item)

    # ── Transcrição via OpenAI API ────────────────────────────────────────────

    def _transcribe_openai(self, item: QueueItem):
        item.status   = "processing"
        item.progress = 0.0
        self.after(0, self._refresh, item)
        self.after(0, self._set_status, f"Enviando para API: {item.name}")

        tmp_path = None
        try:
            from openai import OpenAI

            api_key    = self.api_key_var.get().strip()
            model_name = self.openai_model_var.get()
            client     = OpenAI(api_key=api_key)

            audio_path = item.path
            # Comprime se > 24 MB (limite da API é 25 MB)
            if item.path.stat().st_size > 24 * 1024 * 1024:
                self.after(0, self._set_status, f"Comprimindo audio: {item.name}")
                tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
                tmp.close()
                tmp_path = Path(tmp.name)
                subprocess.run(
                    ["ffmpeg", "-i", str(item.path),
                     "-vn", "-ar", "16000", "-ac", "1", "-b:a", "32k",
                     "-y", str(tmp_path)],
                    capture_output=True, check=True,
                )
                audio_path = tmp_path

            self.after(0, self._set_status, f"Aguardando resposta da API: {item.name}")

            with open(audio_path, "rb") as f:
                response = client.audio.transcriptions.create(
                    model=model_name,
                    file=f,
                    response_format="verbose_json",
                    timestamp_granularities=["segment"],
                )

            # Normaliza segmentos (verbose_json retorna lista de dicts ou objetos)
            raw_segs = getattr(response, "segments", None) or []
            duration = getattr(response, "duration", None) or _get_duration(item.path)
            item.language = getattr(response, "language", "")
            item.duration = duration or 0.0

            if raw_segs:
                segments = [_ApiSegment(s) for s in raw_segs]
            else:
                # Fallback: texto sem timestamps → um bloco só
                text = getattr(response, "text", "")
                segments = [_ApiSegment({"start": 0.0, "end": duration or 0.0, "text": text})]

            _write_outputs(segments, item, self.output_dir,
                           self.want_txt.get(), self.want_srt.get())
            item.status   = "done"
            item.progress = 100.0

        except Exception as exc:
            item.status    = "error"
            item.error_msg = str(exc)
            item.progress  = 0.0
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()

        self.after(0, self._refresh, item)

    # ── Utilitários ───────────────────────────────────────────────────────────

    def _refresh(self, item: QueueItem):
        for w in self._widgets:
            if w.item is item:
                w.refresh()
                break

    def _set_status(self, text: str):
        self.status_lbl.configure(text=text)

    def _all_done(self):
        done = sum(1 for it in self._items if it.status == "done")
        errs = sum(1 for it in self._items if it.status == "error")
        msg  = f"Concluido — {done} transcrito{'s' if done != 1 else ''}"
        if errs:
            msg += f", {errs} com erro"
        self._set_status(msg)
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled", fg_color=SECONDARY, text_color=MUTED)


# ─── Helpers ───────────────────────────────────────────────────────────────────

class _ApiSegment:
    """Normaliza segmentos da API (dict ou objeto) para interface uniforme."""
    def __init__(self, raw):
        if isinstance(raw, dict):
            self.start = float(raw.get("start", 0))
            self.end   = float(raw.get("end", 0))
            self.text  = raw.get("text", "")
        else:
            self.start = float(getattr(raw, "start", 0))
            self.end   = float(getattr(raw, "end", 0))
            self.text  = getattr(raw, "text", "")


def _write_outputs(segments, item: QueueItem, output_dir: Path,
                   want_txt: bool, want_srt: bool):
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = item.path.stem

    if want_txt:
        with open(output_dir / f"{stem}.txt", "w", encoding="utf-8") as f:
            for seg in segments:
                f.write(seg.text.strip() + "\n")

    if want_srt:
        with open(output_dir / f"{stem}.srt", "w", encoding="utf-8") as f:
            for i, seg in enumerate(segments, 1):
                f.write(f"{i}\n")
                f.write(f"{_ts(seg.start)} --> {_ts(seg.end)}\n")
                f.write(seg.text.strip() + "\n\n")


def _vsep(parent, padx=16):
    """Divisor vertical fino para separar colunas em linha."""
    ctk.CTkFrame(parent, width=1, fg_color=BORDER).pack(
        side="left", fill="y", padx=padx, pady=4)


def _hsep(parent, pady=12):
    """Divisor horizontal fino entre seções verticais."""
    ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(fill="x", pady=pady)


def _parse_drop(data: str) -> list[str]:
    import sys
    result = []
    # Windows retorna caminhos com \ — normaliza para /
    if sys.platform == "win32":
        data = data.replace("\\", "/")
    for bracketed, plain in re.findall(r"\{([^}]+)\}|(\S+)", data):
        p = (bracketed or plain).strip()
        if not p:
            continue
        # Remove aspas que alguns sistemas adicionam
        p = p.strip('"').strip("'")
        try:
            p_path = Path(p)
            if p_path.exists():
                result.append(str(p_path))
        except Exception:
            pass
    return result


def _shorten(path: Path, n: int = 44) -> str:
    s = str(path)
    return ("..." + s[-(n - 3):]) if len(s) > n else s


def _get_duration(path: Path) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "quiet", "-print_format", "json",
             "-show_format", str(path)],
            capture_output=True, text=True, timeout=10,
        )
        return float(json.loads(r.stdout)["format"]["duration"])
    except Exception:
        return 0.0


def _ts(s: float) -> str:
    h, rem = divmod(int(s), 3600)
    m, sec = divmod(rem, 60)
    ms = int((s - int(s)) * 1000)
    return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"


# ─── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()
