# -*- coding: utf-8 -*-
"""
Janela principal do RD5 PageStudio.

Estrutura da tela (no espírito do FrontPage 2000):

    barra "Padrão"      -> novo / abrir / salvar / recortar / colar / desfazer...
    barra "Formatação"  -> estilo, negrito, itálico, alinhamento, cor, tamanho
    Lista de Pastas     -> árvore do site, com filtro e menu de contexto
    área da página      -> abas inferiores Design | Código | Visualizar
    barra de status     -> mensagem, posição, palavras, codificação e modo
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import threading
import time
import tkinter as tk
import tkinter.font as tkfont
import webbrowser
import pathlib
from tkinter import ttk, filedialog, messagebox, colorchooser
from typing import Dict, List, Optional

from ps_core import (
    APP, VERSION, FACE, FACE_HI, FONT, FONT_S, NAVY,
    HTML_EXTS, OPEN_FILETYPES, SAVE_FILETYPES, IMAGE_FILETYPES,
    STYLES, LINE_TAGS, BULLET, HR_TEXT, SPECIAL_CHARS,
    DesignHistory, DesignParser, MatchFinder, ProtectedBlocks, Settings,
    autosave_path, find_autosaves, clear_autosaves,
    count_words, design_to_html, extract_protected, file_stat_signature,
    get_meta, get_title, merge_body, new_page, read_document, replace_all,
    set_body_attrs, set_meta, set_title, table_html, validate_html, write_text,
)
from ps_gui.dialogs import LinkDialog, PagePropertiesDialog, ReportDialog, TableDialog
from ps_gui.panels import FindPanel, FolderPanel
from ps_gui.widgets import Tip

try:  # visualização embutida (opcional)
    from tkinterweb import HtmlFrame
    HAS_WEB = True
except Exception:  # pragma: no cover - depende do ambiente
    HtmlFrame = None
    HAS_WEB = False

WATCH_MS = 2500          # intervalo da checagem de edição externa
FIND_LIMIT = 999         # acima disso não contamos as ocorrências uma a uma


class App(tk.Tk):
    """Aplicativo completo."""

    # ============================================================== início
    def __init__(self, path: Optional[str] = None):
        super().__init__()
        self.settings = Settings.load()
        try:
            self.geometry(self.settings.geometry or "1180x760")
        except tk.TclError:  # pragma: no cover - geometria inválida gravada
            self.geometry("1180x760")
        self.minsize(880, 560)
        self.configure(bg=FACE)

        # estado do documento
        self.path: Optional[str] = None
        self.encoding = "utf-8"
        self.bom = False
        self.signature = None
        self.mode = "design"
        self.dirty = False
        self.design_mod = False
        self.design_stale = True
        self.untitled = 1
        self.blocks = ProtectedBlocks()
        self.history = None
        self._hist_job = None
        self._hl_job = None
        self._autosave_job = None
        self._watch_job = None
        self._watch_paused = False
        self._pip_job = None
        self._lossy_warned = False
        self.frames: Dict[str, tk.Widget] = {}

        self._style()
        self._fonts()
        self._build_menu()
        self._build_toolbars()
        self._build_body()
        self._build_status()
        self._bind_keys()
        self.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.bind("<Configure>", self._remember_geometry, add="+")

        self.new_file(initial=True)
        self.folder.set_root(self.settings.root_dir or os.getcwd())
        self._build_recent_menu()
        if path and os.path.isfile(path):
            self.open_file(path)
        self.after(600, self.offer_recovery)
        clear_autosaves()
        self._schedule_watch()
        self._schedule_autosave()
        self.update_title()
        self.update_status()

    # ============================================================ aparência
    def _style(self) -> None:
        st = ttk.Style(self)
        for theme in ("winnative", "vista", "clam", "default"):
            if theme in st.theme_names():
                try:
                    st.theme_use(theme)
                    break
                except tk.TclError:  # pragma: no cover
                    continue
        st.configure("Treeview", font=FONT, rowheight=18)
        st.configure("TCombobox", font=FONT)

    def _fonts(self) -> None:
        size = max(8, min(24, int(self.settings.font_size or 12)))
        self.f_base = tkfont.Font(family="Times New Roman", size=size)
        self.f_bold = self.f_base.copy(); self.f_bold.configure(weight="bold")
        self.f_ital = self.f_base.copy(); self.f_ital.configure(slant="italic")
        self.f_bi = self.f_base.copy(); self.f_bi.configure(weight="bold", slant="italic")
        self.f_h = {
            "h1": tkfont.Font(family="Times New Roman", size=size * 2, weight="bold"),
            "h2": tkfont.Font(family="Times New Roman", size=int(size * 1.5), weight="bold"),
            "h3": tkfont.Font(family="Times New Roman", size=int(size * 1.15), weight="bold"),
        }
        self.f_pre = tkfont.Font(family="Courier New", size=size - 1)
        self.f_code = tkfont.Font(family="Courier New", size=10)

    def _sep(self, parent) -> None:
        tk.Frame(parent, width=2, bd=1, relief="sunken", bg=FACE).pack(
            side="left", fill="y", padx=3, pady=2)

    def _btn(self, parent, text, cmd, tip, fg="black", font=("Tahoma", 10), width=None):
        b = tk.Button(parent, text=text, command=cmd, relief="flat", bd=1, bg=FACE,
                      activebackground=FACE_HI, overrelief="raised", font=font,
                      padx=4, pady=1, takefocus=0, fg=fg, width=width)
        b.pack(side="left", padx=1, pady=1)
        Tip(b, tip)
        return b

    # ================================================================ menus
    def _build_menu(self) -> None:
        mb = tk.Menu(self)
        self.config(menu=mb)
        self.menubar = mb

        m = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Arquivo", menu=m)
        m.add_command(label="Novo\tCtrl+N", command=self.new_file)
        m.add_command(label="Abrir...\tCtrl+O", command=self.open_file)
        m.add_command(label="Abrir pasta...", command=self.open_folder)
        self.recent_menu = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Documentos recentes", menu=self.recent_menu)
        m.add_separator()
        m.add_command(label="Salvar\tCtrl+S", command=self.save)
        m.add_command(label="Salvar como...", command=self.save_as)
        m.add_command(label="Salvar cópia...", command=self.save_copy)
        m.add_separator()
        m.add_command(label="Propriedades da página...", command=self.page_props)
        m.add_command(label="Visualizar no navegador\tF12", command=self.preview_browser)
        m.add_separator()
        m.add_command(label="Sair", command=self.quit_app)

        m = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Editar", menu=m)
        m.add_command(label="Desfazer\tCtrl+Z", command=self.undo)
        m.add_command(label="Refazer\tCtrl+Y", command=self.redo)
        m.add_separator()
        m.add_command(label="Recortar\tCtrl+X", command=lambda: self.ev("<<Cut>>"))
        m.add_command(label="Copiar\tCtrl+C", command=lambda: self.ev("<<Copy>>"))
        m.add_command(label="Colar\tCtrl+V", command=lambda: self.ev("<<Paste>>"))
        m.add_command(label="Selecionar tudo\tCtrl+A", command=self.select_all)
        m.add_separator()
        m.add_command(label="Localizar...\tCtrl+F", command=self.find)
        m.add_command(label="Substituir...\tCtrl+H", command=self.replace)
        m.add_command(label="Localizar próximo\tF3", command=self.find_next)
        m.add_command(label="Localizar anterior\tShift+F3", command=self.find_prev)

        m = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Exibir", menu=m)
        m.add_command(label="Design\tCtrl+1", command=lambda: self.set_mode("design"))
        m.add_command(label="Código\tCtrl+2", command=lambda: self.set_mode("code"))
        m.add_command(label="Visualizar\tCtrl+3", command=lambda: self.set_mode("preview"))
        m.add_separator()
        self.var_folders = tk.BooleanVar(value=True)
        m.add_checkbutton(label="Lista de Pastas", variable=self.var_folders,
                          command=self.toggle_folders)
        self.var_autosave = tk.BooleanVar(value=bool(self.settings.autosave))
        m.add_checkbutton(label="Recuperação automática", variable=self.var_autosave,
                          command=self._toggle_autosave)
        self.var_watch = tk.BooleanVar(value=bool(self.settings.watch_file))
        m.add_checkbutton(label="Avisar se o arquivo mudar no disco", variable=self.var_watch,
                          command=self._toggle_watch)

        m = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Inserir", menu=m)
        m.add_command(label="Hyperlink...\tCtrl+K", command=self.ins_link)
        m.add_command(label="Link de e-mail...", command=lambda: self.ins_link("mailto:"))
        m.add_command(label="Imagem...", command=self.ins_image)
        m.add_command(label="Tabela...", command=self.ins_table)
        m.add_command(label="Linha horizontal", command=self.ins_hr)
        m.add_command(label="Comentário HTML", command=self.ins_comment)
        m.add_command(label="Data de hoje", command=self.ins_date)
        m.add_separator()
        chars = tk.Menu(m, tearoff=0)
        m.add_cascade(label="Caractere especial", menu=chars)
        for label, value in SPECIAL_CHARS:
            chars.add_command(label=label, command=lambda v=value: self.ins_text(v))

        m = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Formatar", menu=m)
        m.add_command(label="Negrito\tCtrl+B", command=lambda: self.fmt("bold"))
        m.add_command(label="Itálico\tCtrl+I", command=lambda: self.fmt("italic"))
        m.add_command(label="Sublinhado\tCtrl+U", command=lambda: self.fmt("underline"))
        m.add_separator()
        m.add_command(label="Cor da fonte...", command=self.pick_color)
        m.add_command(label="Limpar formatação", command=self.clear_format)
        m.add_separator()
        m.add_command(label="Alinhar à esquerda", command=lambda: self.fmt("align", "left"))
        m.add_command(label="Centralizar", command=lambda: self.fmt("align", "center"))
        m.add_command(label="Alinhar à direita", command=lambda: self.fmt("align", "right"))
        m.add_separator()
        m.add_command(label="Lista com marcadores", command=lambda: self.fmt("style", "Lista com marcadores"))
        m.add_command(label="Título 1", command=lambda: self.fmt("style", "Título 1"))
        m.add_command(label="Título 2", command=lambda: self.fmt("style", "Título 2"))
        m.add_command(label="Título 3", command=lambda: self.fmt("style", "Título 3"))
        m.add_command(label="Pré-formatado", command=lambda: self.fmt("style", "Pré-formatado"))
        m.add_command(label="Normal", command=lambda: self.fmt("style", "Normal"))

        m = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Ferramentas", menu=m)
        m.add_command(label="Localizar e substituir...\tCtrl+H", command=self.replace)
        m.add_command(label="Verificar HTML", command=self.check_html)
        m.add_command(label="Contar palavras", command=self.word_count)
        m.add_command(label="Abrir pasta no sistema", command=self.reveal_current)
        m.add_separator()
        m.add_command(label="Instalar visualização embutida...", command=self.install_web)

        m = tk.Menu(mb, tearoff=0)
        mb.add_cascade(label="Ajuda", menu=m)
        m.add_command(label="Atalhos de teclado", command=self.shortcuts)
        m.add_command(label="Sobre", command=self.about)

    def _build_recent_menu(self) -> None:
        self.recent_menu.delete(0, "end")
        items = self.settings.recent or []
        if not items:
            self.recent_menu.add_command(label="(nenhum documento recente)", state="disabled")
            return
        for path in items:
            label = os.path.basename(path) or path
            self.recent_menu.add_command(
                label=f"{label}   —   {os.path.dirname(path)}",
                command=lambda p=path: self.open_file(p))
        self.recent_menu.add_separator()
        self.recent_menu.add_command(label="Limpar lista", command=self.clear_recent)

    def clear_recent(self) -> None:
        self.settings.recent = []
        self.settings.save()
        self._build_recent_menu()

    # ============================================================== barras
    def _build_toolbars(self) -> None:
        bar1 = tk.Frame(self, bg=FACE)
        bar1.pack(fill="x")
        self._btn(bar1, "\U0001F4C4", self.new_file, "Nova página (Ctrl+N)")
        self._btn(bar1, "\U0001F4C2", self.open_file, "Abrir (Ctrl+O)")
        self._btn(bar1, "\U0001F4BE", self.save, "Salvar (Ctrl+S)")
        self._sep(bar1)
        self._btn(bar1, "\u2702", lambda: self.ev("<<Cut>>"), "Recortar (Ctrl+X)")
        self._btn(bar1, "\u29C9", lambda: self.ev("<<Copy>>"), "Copiar (Ctrl+C)")
        self._btn(bar1, "\U0001F4CB", lambda: self.ev("<<Paste>>"), "Colar (Ctrl+V)")
        self._sep(bar1)
        self._btn(bar1, "\u21B6", self.undo, "Desfazer (Ctrl+Z)")
        self._btn(bar1, "\u21B7", self.redo, "Refazer (Ctrl+Y)")
        self._sep(bar1)
        self._btn(bar1, "\U0001F517", self.ins_link, "Inserir hyperlink (Ctrl+K)")
        self._btn(bar1, "\U0001F5BC", self.ins_image, "Inserir imagem")
        self._btn(bar1, "\u25A6", self.ins_table, "Inserir tabela")
        self._btn(bar1, "\u2501", self.ins_hr, "Linha horizontal")
        self._sep(bar1)
        self._btn(bar1, "\U0001F50D", self.find, "Localizar (Ctrl+F)")
        self._sep(bar1)
        self._btn(bar1, "\U0001F310", self.preview_browser, "Visualizar no navegador (F12)")
        tk.Frame(self, height=2, bd=1, relief="sunken", bg=FACE).pack(fill="x")

        bar2 = tk.Frame(self, bg=FACE)
        bar2.pack(fill="x")
        self.style_var = tk.StringVar(value="Normal")
        cb = ttk.Combobox(bar2, textvariable=self.style_var, values=list(STYLES),
                          state="readonly", width=20, font=FONT)
        cb.pack(side="left", padx=4, pady=2)
        cb.bind("<<ComboboxSelected>>", lambda _e: self.fmt("style", self.style_var.get()))
        Tip(cb, "Estilo do parágrafo")
        self._sep(bar2)
        bold = ("Times New Roman", 11, "bold")
        self._btn(bar2, "N", lambda: self.fmt("bold"), "Negrito (Ctrl+B)", font=bold, width=2)
        self._btn(bar2, "I", lambda: self.fmt("italic"), "Itálico (Ctrl+I)",
                  font=("Times New Roman", 11, "italic"), width=2)
        self._btn(bar2, "S", lambda: self.fmt("underline"), "Sublinhado (Ctrl+U)",
                  font=("Times New Roman", 11, "underline"), width=2)
        self._btn(bar2, "A", self.pick_color, "Cor da fonte", fg="#C00000",
                  font=("Tahoma", 10, "bold"), width=2)
        self._sep(bar2)
        self._btn(bar2, "Esq", lambda: self.fmt("align", "left"), "Alinhar à esquerda", font=FONT_S)
        self._btn(bar2, "Cen", lambda: self.fmt("align", "center"), "Centralizar", font=FONT_S)
        self._btn(bar2, "Dir", lambda: self.fmt("align", "right"), "Alinhar à direita", font=FONT_S)
        self._btn(bar2, "\u2022\u2261", lambda: self.fmt("style", "Lista com marcadores"),
                  "Lista com marcadores", font=FONT)
        self._sep(bar2)
        self._btn(bar2, "T-", self.bigger_font, "Aumentar o texto do modo Design", font=FONT_S)
        self._btn(bar2, "T+", self.smaller_font, "Diminuir o texto do modo Design", font=FONT_S)
        self._sep(bar2)
        self._btn(bar2, "\u2713", self.check_html, "Verificar HTML", font=FONT_S)
        tk.Frame(self, height=2, bd=1, relief="sunken", bg=FACE).pack(fill="x")

    # ================================================================ corpo
    def _scroll_text(self, parent, **kw):
        frame = tk.Frame(parent)
        widget = tk.Text(frame, **kw)
        ys = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        if kw.get("wrap") == "none":
            xs = ttk.Scrollbar(frame, orient="horizontal", command=widget.xview)
            widget.configure(xscrollcommand=xs.set)
            xs.pack(side="bottom", fill="x")
        widget.pack(side="left", fill="both", expand=True)
        return frame, widget

    def _build_body(self) -> None:
        pw = tk.PanedWindow(self, orient="horizontal", sashwidth=4, bg=FACE, bd=0)
        self.pane = pw
        pw.pack(fill="both", expand=True, padx=2, pady=2)

        self.folder = FolderPanel(pw, on_open=self.open_file, on_reveal=self.reveal)
        pw.add(self.folder, width=220, minsize=130)

        right = tk.Frame(pw, bg=FACE)
        pw.add(right, minsize=420)

        tabrow = tk.Frame(right, bg=FACE)
        tabrow.pack(fill="x")
        self.page_tab = tk.Label(tabrow, text="", bg="white", relief="raised", bd=2,
                                 font=FONT, padx=10, anchor="w")
        self.page_tab.pack(side="left", pady=(2, 0), fill="x", expand=True)

        self.find_panel = FindPanel(right, callbacks={
            "next": self.find_next, "prev": self.find_prev,
            "replace": self.replace_one, "replace_all": self.replace_everything,
            "close": self.hide_find, "changed": self.update_find_count,
        })

        self.content = tk.Frame(right, bd=2, relief="sunken", bg="white")
        self.content.pack(fill="both", expand=True)

        frame, self.text = self._scroll_text(
            self.content, wrap="word", undo=False, font=self.f_base, bg="white",
            relief="flat", bd=0, padx=14, pady=10, insertwidth=2,
            selectbackground=NAVY, selectforeground="white")
        self.frames["design"] = frame
        self._config_design_tags()
        self.text.bind("<<Modified>>", self._design_modified)
        self.text.bind("<KeyRelease-Return>", self._design_return)
        self.history = DesignHistory(self.text)

        frame, self.code = self._scroll_text(
            self.content, wrap="none", undo=True, font=self.f_code, bg="white",
            relief="flat", bd=0, padx=6, pady=4, insertwidth=2, tabs=("0.5c",),
            selectbackground=NAVY, selectforeground="white")
        self.frames["code"] = frame
        self.code.tag_configure("tag", foreground="#800000")
        self.code.tag_configure("attr", foreground="#C00000")
        self.code.tag_configure("str", foreground="#0000C0")
        self.code.tag_configure("cmt", foreground="#008000")
        self.code.tag_configure("found", background="#FFFF00")
        self.code.bind("<<Modified>>", self._code_modified)
        self.code.bind("<Tab>", self._code_tab)
        self.code.bind("<Shift-Tab>", self._code_shift_tab)

        self.preview_frame = tk.Frame(self.content, bg="white")
        self.frames["preview"] = self.preview_frame
        self.web = None
        self._build_preview()

        self.frames["design"].pack(fill="both", expand=True)

        bot = tk.Frame(right, bg=FACE)
        bot.pack(fill="x")
        self.modevar = tk.StringVar(value="design")
        for value, label in (("design", "\u270E Design"), ("code", "\u2039/\u203A Código"),
                             ("preview", "\U0001F50D Visualizar")):
            tk.Radiobutton(bot, text=label, value=value, variable=self.modevar,
                           indicatoron=False, command=lambda v=value: self.set_mode(v),
                           bg=FACE, selectcolor="white", font=FONT, padx=12, pady=1,
                           bd=2, takefocus=0).pack(side="left", padx=(0, 1))
        self._btn(bot, "\u21bb", self.refresh_preview, "Atualizar a visualização (F5)",
                  font=FONT_S).pack(side="right", padx=2, pady=1)

    def _build_preview(self) -> None:
        for child in self.preview_frame.winfo_children():
            child.destroy()
        self.web = None
        if HAS_WEB and HtmlFrame is not None:
            try:
                self.web = HtmlFrame(self.preview_frame, messages_enabled=False)
                self.web.pack(fill="both", expand=True)
                return
            except Exception:  # pragma: no cover - biblioteca quebrada
                self.web = None
        tk.Label(self.preview_frame, bg="white", font=("Tahoma", 10), justify="center",
                 text="Visualização embutida indisponível.\n"
                      "Ela é opcional:  pip install tkinterweb\n\n"
                      "Enquanto isso, use o navegador (F12).").pack(pady=(70, 10))
        tk.Button(self.preview_frame, text="\U0001F310  Abrir no navegador", font=FONT,
                  command=self.preview_browser, padx=10).pack()

    def _config_design_tags(self) -> None:
        t = self.text
        t.tag_configure("bold", font=self.f_bold)
        t.tag_configure("italic", font=self.f_ital)
        t.tag_configure("bi", font=self.f_bi)
        t.tag_configure("underline", underline=True)
        for key in ("h1", "h2", "h3"):
            t.tag_configure(key, font=self.f_h[key], spacing1=6, spacing3=4)
        t.tag_configure("pre", font=self.f_pre, background="#F4F4F4")
        t.tag_configure("center", justify="center")
        t.tag_configure("right", justify="right")
        t.tag_configure("li", lmargin1=24, lmargin2=38)
        t.tag_configure("hr", foreground="#808080", justify="center")
        t.tag_configure("found", background="#FFFF00")
        t.tag_raise("sel")

    def _build_status(self) -> None:
        bar = tk.Frame(self, bg=FACE)
        bar.pack(fill="x", side="bottom")
        self.st_msg = tk.Label(bar, text="Pronto", bg=FACE, font=FONT, anchor="w",
                               relief="sunken", bd=1)
        self.st_msg.pack(side="left", fill="x", expand=True, padx=(2, 1), pady=2)
        self.st_stats = tk.Label(bar, text="", bg=FACE, font=FONT, width=22, relief="sunken", bd=1)
        self.st_stats.pack(side="left", padx=1, pady=2)
        self.st_pos = tk.Label(bar, text="Lin 1, Col 1", bg=FACE, font=FONT, width=14,
                               relief="sunken", bd=1)
        self.st_pos.pack(side="left", padx=1, pady=2)
        self.st_enc = tk.Label(bar, text="UTF-8", bg=FACE, font=FONT, width=10,
                               relief="sunken", bd=1)
        self.st_enc.pack(side="left", padx=1, pady=2)
        self.st_mode = tk.Label(bar, text="Design", bg=FACE, font=FONT, width=11,
                                relief="sunken", bd=1)
        self.st_mode.pack(side="left", padx=(1, 2), pady=2)

    def _bind_keys(self) -> None:
        bind = self.bind_all
        for seq, cmd in (
            ("<Control-n>", self.new_file), ("<Control-o>", self.open_file),
            ("<Control-s>", self.save), ("<Control-f>", self.find),
            ("<Control-h>", self.replace), ("<Control-k>", self.ins_link),
            ("<Control-z>", self.undo), ("<Control-y>", self.redo),
            ("<Control-a>", self.select_all), ("<Control-1>", lambda: self.set_mode("design")),
            ("<Control-2>", lambda: self.set_mode("code")), ("<Control-3>", lambda: self.set_mode("preview")),
            ("<F12>", self.preview_browser), ("<F5>", self.refresh_preview),
            ("<F3>", self.find_next), ("<Shift-F3>", self.find_prev),
            ("<Escape>", self.hide_find),
        ):
            bind(seq, lambda _e, f=cmd: self._call(f))
        for widget in (self.text, self.code):
            widget.bind("<Control-b>", lambda e: (self.fmt("bold"), "break")[1])
            widget.bind("<Control-i>", lambda e: (self.fmt("italic"), "break")[1])
            widget.bind("<Control-u>", lambda e: (self.fmt("underline"), "break")[1])
            widget.bind("<KeyRelease>", self._pos_event, add="+")
            widget.bind("<ButtonRelease-1>", self._pos_event, add="+")
        self.code.bind("<KeyRelease>", self._schedule_hl, add="+")

    def _call(self, func, *args):
        """Executa um comando de menu/atalho sem propagar o evento."""
        func(*args)
        return "break"

    # ============================================================== estados
    def _design_modified(self, _event=None) -> None:
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self._touch_design()
            self._schedule_snapshot()

    def _code_modified(self, _event=None) -> None:
        if self.code.edit_modified():
            self.code.edit_modified(False)
            self.design_stale = True
            self.dirty = True
            self.update_title()
            self.update_status()

    def _touch_design(self) -> None:
        self.design_mod = True
        self.dirty = True
        self.update_title()
        self.update_status()

    def update_title(self) -> None:
        name = os.path.basename(self.path) if self.path else f"nova_pagina_{self.untitled}.htm"
        mark = " *" if self.dirty else ""
        self.title(f"{name}{mark} — {APP} {VERSION}")
        self.page_tab.config(text=f"{name}{mark}    {os.path.dirname(self.path) if self.path else '(não gravado)'}")

    def msg(self, text: str) -> None:
        self.st_msg.config(text=text)

    def _pos_event(self, _event=None) -> None:
        self.update_status()

    def update_status(self) -> None:
        widget = self.text if self.mode == "design" else self.code
        if self.mode != "preview":
            try:
                line, col = widget.index("insert").split(".")
                self.st_pos.config(text=f"Lin {line}, Col {int(col) + 1}")
            except tk.TclError:  # pragma: no cover
                pass
        self.st_mode.config(text={"design": "Design", "code": "Código",
                                  "preview": "Visualizar"}[self.mode])
        self.st_enc.config(text=self.encoding.upper() + (" BOM" if self.bom else ""))
        if self.mode == "design":
            text = self.text.get("1.0", "end-1c")
            words = count_words(text)
            self.st_stats.config(text=f"{words} palavra(s), {len(text)} caract.")
            tags = self.text.tag_names("insert linestart")
            current = "Normal"
            for name, key in STYLES.items():
                if key and key in tags:
                    current = name
            if self.style_var.get() != current:
                self.style_var.set(current)
        else:
            size = len(self.code.get("1.0", "end-1c").encode("utf-8", "ignore"))
            self.st_stats.config(text=f"{size / 1024:.1f} KB")

    def _remember_geometry(self, _event=None) -> None:
        if getattr(self, "_geom_job", None):
            return
        self._geom_job = self.after(1200, self._save_geometry)

    def _save_geometry(self) -> None:
        self._geom_job = None
        try:
            self.settings.geometry = self.geometry()
            self.settings.save()
        except tk.TclError:  # pragma: no cover
            pass

    # ================================================================ modos
    def set_mode(self, mode: str) -> None:
        if mode == self.mode:
            if mode == "preview":
                self.render_preview()
            return
        old = self.mode
        if old == "design":
            self.sync_design_to_code()
        self.frames[old].pack_forget()
        if mode == "design" and self.design_stale:
            self.load_design(self.code.get("1.0", "end-1c"))
        elif mode == "preview":
            self.render_preview()
        elif mode == "code":
            self.highlight()
        self.frames[mode].pack(fill="both", expand=True)
        self.mode = mode
        self.modevar.set(mode)
        self.update_status()
        target = {"design": self.text, "code": self.code}.get(mode, self)
        target.focus_set()

    def toggle_folders(self) -> None:
        if self.var_folders.get():
            self.pane.add(self.folder, before=self.pane.panes()[-1], width=220, minsize=130)
        else:
            try:
                self.pane.forget(self.folder)
            except tk.TclError:  # pragma: no cover
                pass

    def get_html(self) -> str:
        """HTML completo do documento (sincronizando o modo Design se preciso)."""
        if self.mode == "design":
            self.sync_design_to_code()
        return self.code.get("1.0", "end-1c")

    def sync_design_to_code(self) -> None:
        if not self.design_mod:
            return
        body = design_to_html(self.text, self.blocks)
        merged = merge_body(self.code.get("1.0", "end-1c"), body, title=get_title(self.code.get("1.0", "end-1c")))
        self.code.delete("1.0", "end")
        self.code.insert("1.0", merged)
        self.code.edit_modified(False)
        self.design_mod = False
        self.design_stale = False
        self.highlight()

    def render_preview(self) -> None:
        if not self.web:
            return
        html = self.get_html()
        base = None
        if self.path:
            try:
                base = pathlib.Path(os.path.dirname(os.path.abspath(self.path))).as_uri() + "/"
            except OSError:  # pragma: no cover
                base = None
        try:
            if base:
                self.web.load_html(html, base_url=base)
            else:
                self.web.load_html(html)
        except Exception as ex:  # pragma: no cover - motor embutido
            self.msg(f"Falha ao renderizar: {ex}")

    def refresh_preview(self) -> None:
        if self.mode == "preview":
            self.render_preview()
            self.msg("Visualização atualizada.")
        elif self.path:
            self.folder.refresh()
            self.msg("Lista de Pastas atualizada.")
        else:
            self.render_preview()

    # ======================================================= Design ⇄ HTML
    def ensure_tag(self, name: str) -> bool:
        t = self.text
        try:
            if name.startswith("a:"):
                t.tag_configure(name, foreground="#0000FF", underline=True)
            elif name.startswith("c:"):
                t.tag_configure(name, foreground=name[2:])
            elif name.startswith("s:"):
                t.tag_configure(name, font=self._scaled_font(int(name[2:] or 3)))
            elif name.startswith("img:"):
                t.tag_configure(name, background="#E4E4E4", foreground="#404040")
            elif name.startswith("pb:"):
                t.tag_configure(name, background="#EFEFEF", foreground="#606060",
                                font=("Tahoma", 9, "italic"))
            else:
                return name in t.tag_names()
        except tk.TclError:  # pragma: no cover - cor inválida no HTML
            return False
        t.tag_raise("sel")
        return True

    def _scaled_font(self, size: int):
        size = max(1, min(7, size))
        return tkfont.Font(family="Times New Roman", size=int(self.f_base.cget("size")) + (size - 3) * 2)

    def load_design(self, code: str) -> None:
        """Reconstrói o modo Design a partir do HTML."""
        stripped, blocks = extract_protected(code)
        parser = DesignParser()
        parser.feed(stripped)
        parser.close()

        t = self.text
        t.configure(undo=False)
        t.delete("1.0", "end")
        for text, tags in parser.out:
            tags = tuple(tag for tag in tags if self.ensure_tag(tag))
            t.insert("end", text, tags)
        self.blocks = blocks
        self.history = DesignHistory(t)
        t.edit_reset()
        t.edit_modified(False)
        t.configure(undo=False)
        self.design_mod = False
        self.design_stale = False
        self.refresh_bi()
        self._warn_lossy(parser, blocks)

    def _warn_lossy(self, parser: DesignParser, blocks: ProtectedBlocks) -> None:
        if self._lossy_warned or not (parser.lossy or blocks):
            return
        self._lossy_warned = True
        kinds = sorted({blocks.items[i][0] for i in range(len(blocks))}) if blocks else []
        detail = ", ".join(kinds) if kinds else "tabelas, formulários ou scripts"
        self.msg("A página tem elementos avançados — eles estão protegidos no modo Design.")
        messagebox.showinfo(
            APP,
            "Esta página contém elementos avançados (" + detail + ").\n\n"
            "No modo Design eles aparecem como uma linha cinza \"conteúdo protegido\" e são "
            "devolvidos ao arquivo exatamente como estavam, mesmo que você edite o resto da "
            "página em Design.\n\n"
            "Para editar o conteúdo desses elementos, use a aba Código.")

    @staticmethod
    def _inl(tag: str) -> bool:
        return tag in ("bold", "italic", "underline") or tag.startswith(("a:", "c:", "img:", "s:"))

    def refresh_bi(self) -> None:
        """Marca os trechos que são negrito e itálico ao mesmo tempo."""
        t = self.text
        t.tag_remove("bi", "1.0", "end")
        bold = self._ranges("bold")
        ital = self._ranges("italic")
        for a, b in bold:
            for c, d in ital:
                start = a if t.compare(a, ">", c) else c
                end = b if t.compare(b, "<", d) else d
                if t.compare(start, "<", end):
                    t.tag_add("bi", start, end)

    def _ranges(self, tag: str):
        r = self.text.tag_ranges(tag)
        return [(str(r[i]), str(r[i + 1])) for i in range(0, len(r), 2)]

    def _page_title(self) -> str:
        return get_title(self.code.get("1.0", "end-1c")) or "Nova Página"

    # =================================================== histórico (Design)
    def _schedule_snapshot(self) -> None:
        if self._hist_job:
            self.after_cancel(self._hist_job)
        self._hist_job = self.after(700, self._capture_history)

    def _capture_history(self) -> None:
        self._hist_job = None
        if self.history is not None:
            self.history.push()

    def _push_history(self) -> None:
        if self._hist_job:
            self.after_cancel(self._hist_job)
            self._hist_job = None
        if self.history is not None:
            self.history.push()

    def undo(self) -> None:
        if self.mode == "design" and self.history is not None:
            if not self.history.can_undo():
                self.msg("Nada para desfazer.")
                return
            self.history.undo()
            self._touch_design()
            self.msg("Desfeito.")
            return
        if self.mode == "code":
            try:
                self.code.edit_undo()
            except tk.TclError:
                self.msg("Nada para desfazer.")

    def redo(self) -> None:
        if self.mode == "design" and self.history is not None:
            if not self.history.can_redo():
                self.msg("Nada para refazer.")
                return
            self.history.redo()
            self._touch_design()
            self.msg("Refeito.")
            return
        if self.mode == "code":
            try:
                self.code.edit_redo()
            except tk.TclError:
                self.msg("Nada para refazer.")

    # =========================================================== formatação
    def fmt(self, kind: str, arg=None) -> None:
        if self.mode == "preview":
            self.set_mode("design")
        if self.mode == "design":
            self._push_history()
            {"bold": lambda: self.d_toggle("bold"),
             "italic": lambda: self.d_toggle("italic"),
             "underline": lambda: self.d_toggle("underline"),
             "style": lambda: self.d_style(arg),
             "align": lambda: self.d_align(arg)}[kind]()
        elif self.mode == "code":
            if kind in ("bold", "italic", "underline"):
                tag = {"bold": "b", "italic": "i", "underline": "u"}[kind]
                self.code_wrap(f"<{tag}>", f"</{tag}>")
            elif kind == "style":
                key = STYLES.get(arg)
                if key == "li":
                    self.code_wrap("<ul>\n  <li>", "</li>\n</ul>")
                elif key:
                    self.code_wrap(f"<{key}>", f"</{key}>")
                else:
                    self.code_wrap("<p>", "</p>")
            elif kind == "align":
                self.code_wrap(f'<div style="text-align: {arg}">', "</div>")
        self.update_status()

    def _sel(self, widget):
        try:
            return widget.index("sel.first"), widget.index("sel.last")
        except tk.TclError:
            return None

    def d_toggle(self, tag: str) -> None:
        t = self.text
        sel = self._sel(t)
        if not sel:
            self.msg("Selecione o texto antes de formatar.")
            return
        a, b = sel
        if tag in t.tag_names(a):
            t.tag_remove(tag, a, b)
        else:
            t.tag_add(tag, a, b)
        self.refresh_bi()
        self._touch_design()

    def _sel_lines(self):
        t = self.text
        sel = self._sel(t)
        if sel:
            first = int(sel[0].split(".")[0])
            last_line, last_col = sel[1].split(".")
            last = int(last_line)
            if int(last_col) == 0 and last > first:
                last -= 1
            return range(first, last + 1)
        line = int(t.index("insert").split(".")[0])
        return range(line, line + 1)

    def d_style(self, name: str) -> None:
        t = self.text
        tag = STYLES.get(name)
        for n in self._sel_lines():
            start, end = f"{n}.0", f"{n}.end+1c"
            if any(x in t.tag_names(start) for x in ("hr",)) or \
                    any(x.startswith("pb:") for x in t.tag_names(start)):
                continue          # linha horizontal e bloco protegido não viram parágrafo
            was_li = "li" in t.tag_names(start)
            for key in LINE_TAGS:
                t.tag_remove(key, start, end)
            has_bullet = t.get(start, f"{n}.{len(BULLET)}") == BULLET
            if was_li and tag != "li" and has_bullet:
                t.delete(start, f"{n}.{len(BULLET)}")
            if tag == "li" and not has_bullet:
                t.insert(start, BULLET)
            if tag:
                t.tag_add(tag, f"{n}.0", f"{n}.end+1c")
        self._touch_design()

    def d_align(self, align: str) -> None:
        t = self.text
        for n in self._sel_lines():
            start, end = f"{n}.0", f"{n}.end+1c"
            t.tag_remove("center", start, end)
            t.tag_remove("right", start, end)
            if align in ("center", "right"):
                t.tag_add(align, start, end)
        self._touch_design()

    def clear_format(self) -> None:
        """Remove a formatação inline da seleção."""
        if self.mode != "design":
            self.msg("Disponível apenas no modo Design.")
            return
        sel = self._sel(self.text)
        if not sel:
            self.msg("Selecione o texto antes de limpar a formatação.")
            return
        self._push_history()
        for tag in list(self.text.tag_names()):
            if self._inl(tag):
                self.text.tag_remove(tag, *sel)
        self.refresh_bi()
        self._touch_design()
        self.msg("Formatação removida.")

    def _design_return(self, _event) -> None:
        """Enter continua listas e limpa estilos de linha."""
        t = self.text
        n = int(t.index("insert").split(".")[0])
        if n < 2:
            return
        prev, cur = f"{n - 1}.0", f"{n}.0"
        ptags = t.tag_names(prev)
        cur_end = f"{n}.end+1c"
        was_list = "li" in ptags
        for key in LINE_TAGS:
            t.tag_remove(key, cur, cur_end)
        if "hr" in t.tag_names(cur):
            t.tag_remove("hr", cur, cur_end)
        if not was_list:
            return
        if t.get(prev, f"{n - 1}.end").strip() == BULLET.strip():
            t.delete(prev, f"{n - 1}.end")
            for key in LINE_TAGS:
                t.tag_remove(key, prev, f"{n - 1}.end+1c")
        else:
            if t.get(cur, f"{n}.{len(BULLET)}") != BULLET:
                t.insert(cur, BULLET)
            t.tag_add("li", cur, f"{n}.end+1c")

    def bigger_font(self) -> None:
        self._set_font_size(int(self.f_base.cget("size")) + 1)

    def smaller_font(self) -> None:
        self._set_font_size(int(self.f_base.cget("size")) - 1)

    def _set_font_size(self, size: int) -> None:
        size = max(8, min(24, size))
        self.settings.font_size = size
        self._fonts()
        self._config_design_tags()
        self.text.configure(font=self.f_base)
        self.msg(f"Texto do modo Design: {size} pt")

    def code_wrap(self, open_tag: str, close_tag: str) -> None:
        t = self.code
        sel = self._sel(t)
        if not sel:
            t.insert("insert", open_tag + close_tag)
            t.mark_set("insert", f"insert-{len(close_tag)}c")
            return
        a, b = sel
        text = t.get(a, b)
        t.delete(a, b)
        t.insert(a, open_tag + text + close_tag)

    def _code_tab(self, _event):
        return self._code_indent(True)

    def _code_shift_tab(self, _event):
        return self._code_indent(False)

    def _code_indent(self, indent: bool) -> str:
        t = self.code
        sel = self._sel(t)
        if not sel:
            if indent:
                t.insert("insert", "  ")
                return "break"
            return None
        first = int(sel[0].split(".")[0])
        last = int(sel[1].split(".")[0])
        for n in range(first, last + 1):
            if indent:
                t.insert(f"{n}.0", "  ")
            else:
                line = t.get(f"{n}.0", f"{n}.end")
                cut = len(line) - len(line.lstrip(" "))
                if cut:
                    t.delete(f"{n}.0", f"{n}.{min(cut, 2)}")
        return "break"

    def pick_color(self) -> None:
        color = self._ask_color()
        if not color:
            return
        if self.mode == "design":
            sel = self._sel(self.text)
            if not sel:
                self.msg("Selecione o texto antes de aplicar a cor.")
                return
            self._push_history()
            for tag in list(self.text.tag_names()):
                if tag.startswith("c:"):
                    self.text.tag_remove(tag, *sel)
            self.ensure_tag(f"c:{color}")
            self.text.tag_add(f"c:{color}", *sel)
            self._touch_design()
        else:
            self.code_wrap(f'<font color="{color}">', "</font>")

    def _ask_color(self, initial: str = "") -> Optional[str]:
        try:
            return colorchooser.askcolor(color=initial or None, title="Cor da fonte",
                                         parent=self)[1]
        except tk.TclError:  # pragma: no cover - cor inicial inválida
            return colorchooser.askcolor(title="Cor da fonte", parent=self)[1]

    # ============================================================== inserir
    def _insert_design(self, text: str, tags=()) -> None:
        self._push_history()
        self.text.insert("insert", text, tags)
        self.text.see("insert")
        self._touch_design()

    def ins_text(self, text: str) -> None:
        if self.mode == "design":
            self._insert_design(text)
        elif self.mode == "code":
            self.code.insert("insert", text)
        else:
            self.set_mode("design")
            self._insert_design(text)

    def ins_link(self, initial: str = "https://") -> None:
        selection = ""
        if self.mode == "design":
            sel = self._sel(self.text)
            if sel:
                selection = self.text.get(*sel)
        dialog = LinkDialog(self, url=initial, text=selection)
        self.wait_window(dialog)
        data = dialog.result
        if not data:
            return
        url, text = data["url"], data["text"] or data["url"]
        if self.mode == "design":
            self._push_history()
            tag = f"a:{url}"
            self.ensure_tag(tag)
            sel = self._sel(self.text)
            if sel:
                self.text.tag_add(tag, *sel)
            else:
                self.text.insert("insert", text, (tag,))
            self._touch_design()
        elif self.mode == "code":
            self.code_wrap(f'<a href="{url}">', f"{text}</a>")
        else:
            self.set_mode("design")
            self.ins_link(initial)

    def ins_image(self) -> None:
        path = filedialog.askopenfilename(title="Inserir imagem", filetypes=IMAGE_FILETYPES,
                                          parent=self)
        if not path:
            return
        src = path
        if self.path:
            try:
                src = os.path.relpath(path, os.path.dirname(os.path.abspath(self.path)))
                src = src.replace("\\", "/")
            except ValueError:  # unidades diferentes no Windows
                pass
        if self.mode == "design":
            tag = f"img:{src}"
            self.ensure_tag(tag)
            self._insert_design(f"[Imagem: {os.path.basename(path)}]", (tag,))
        elif self.mode == "code":
            self.code.insert("insert", f'<img src="{src}" alt="">')
        else:
            self.set_mode("design")
            self.ins_image()

    def ins_table(self) -> None:
        dialog = TableDialog(self)
        self.wait_window(dialog)
        spec = dialog.result
        if not spec:
            return
        html = table_html(spec["rows"], spec["cols"], border=spec["border"],
                          width=spec["width"], padding=spec["padding"],
                          header=spec["header"])
        if self.mode == "code":
            self.code.insert("insert", html + "\n")
            return
        if self.mode == "preview":
            self.set_mode("code")
            self.code.insert("insert", html + "\n")
            return
        # No modo Design a tabela vira um bloco protegido (conteúdo preservado).
        self._push_history()
        index = len(self.blocks.items)
        self.blocks.items.append(("table", html))
        tag = f"pb:{index}"
        self.ensure_tag(tag)
        label = f"@@RD5PB{index}@@"
        t = self.text
        if t.get("insert linestart", "insert lineend").strip():
            t.insert("insert lineend", "\n")
        t.insert("insert linestart", label + "\n", (tag,))
        self._touch_design()
        self.msg("Tabela inserida (protegida no modo Design; edite-a na aba Código).")

    def ins_hr(self) -> None:
        if self.mode == "design":
            self._push_history()
            t = self.text
            if t.get("insert linestart", "insert lineend").strip():
                t.insert("insert lineend", "\n")
            n = int(t.index("insert").split(".")[0])
            t.insert("insert linestart", HR_TEXT + "\n")
            for key in LINE_TAGS + ("center", "right"):
                t.tag_remove(key, f"{n}.0", f"{n}.end+1c")
            t.tag_add("hr", f"{n}.0", f"{n}.end+1c")
            self._touch_design()
        else:
            self.code.insert("insert", "<hr>\n")

    def ins_comment(self) -> None:
        if self.mode == "design":
            self.set_mode("code")
        self.code.insert("insert", "<!--  -->")
        self.code.mark_set("insert", "insert-3c")
        self.code.focus_set()

    def ins_date(self) -> None:
        self.ins_text(time.strftime("%d/%m/%Y"))

    # =============================================================== código
    def _schedule_hl(self, _event=None) -> None:
        if self._hl_job:
            self.after_cancel(self._hl_job)
        self._hl_job = self.after(350, self.highlight)

    def highlight(self) -> None:
        c = self.code
        for tag in ("tag", "attr", "str", "cmt"):
            c.tag_remove(tag, "1.0", "end")
        src = c.get("1.0", "end-1c")
        if len(src) > 250000:
            return
        for m in re.finditer(r"<!--.*?-->|</?[A-Za-z][^>]*>", src, re.S):
            start, end = m.span()
            piece = m.group()
            index = lambda offset: f"1.0+{offset}c"  # noqa: E731
            if piece.startswith("<!--"):
                c.tag_add("cmt", index(start), index(end))
                continue
            c.tag_add("tag", index(start), index(end))
            for a in re.finditer(r"\s([\w:-]+)=", piece):
                c.tag_add("attr", index(start + a.start(1)), index(start + a.end(1)))
            for q in re.finditer(r'"[^"]*"|\'[^\']*\'', piece):
                c.tag_add("str", index(start + q.start()), index(start + q.end()))

    def check_html(self) -> None:
        issues = validate_html(self.get_html())
        text = "\n".join(f"\u2022 {i}" for i in issues) if issues else \
            "Nenhum problema comum encontrado.\n\n(Esta checagem cobre DOCTYPE, charset, título e " \
            "abertura/fechamento de tags — não substitui o validador da W3C.)"
        ReportDialog(self, "Verificar HTML", text)
        self.msg(f"Verificação concluída: {len(issues)} apontamento(s).")

    def word_count(self) -> None:
        html = self.get_html()
        body = re.sub(r"<[^>]+>", " ", html)
        design_text = self.text.get("1.0", "end-1c")
        ReportDialog(self, "Contar palavras", (
            f"Palavras no modo Design: {count_words(design_text)}\n"
            f"Caracteres no modo Design: {len(design_text)}\n"
            f"Palavras no texto visível (sem tags): {count_words(body)}\n"
            f"Tamanho do arquivo HTML: {len(html.encode('utf-8', 'ignore')) / 1024:.1f} KB"))

    # ================================================================ busca
    def _active_widget(self):
        return {"design": self.text, "code": self.code}.get(self.mode)

    def _show_find(self, replace: bool) -> None:
        widget = self._active_widget()
        if not widget:
            self.set_mode("design")
            widget = self.text
        initial = ""
        sel = self._sel(widget)
        if sel:
            initial = widget.get(*sel)
            if "\n" in initial:
                initial = ""
        self.find_panel.pack(fill="x", before=self.content)
        self.find_panel.show(replace=replace, initial=initial)

    def find(self) -> None:
        self._show_find(False)

    def replace(self) -> None:
        self._show_find(True)

    def hide_find(self) -> None:
        self.find_panel.hide()
        self.find_panel.set_count("")

    def _finder(self) -> Optional[MatchFinder]:
        widget = self._active_widget()
        pattern = self.find_panel.find_var.get()
        if not widget or not pattern:
            return None
        opts = self.find_panel.options()
        finder = MatchFinder(widget, pattern, **opts)
        if finder.error:
            self.find_panel.set_count("expressão inválida")
            return None
        return finder

    def update_find_count(self) -> None:
        finder = self._finder()
        if not finder:
            self.find_panel.set_count("")
            return
        total = finder.count()
        label = f"{total} ocorrência(s)" if total <= FIND_LIMIT else "muitas ocorrências"
        self.find_panel.set_count(label)

    def find_next(self) -> None:
        self._step(False)

    def find_prev(self) -> None:
        self._step(True)

    def _step(self, backward: bool) -> None:
        finder = self._finder()
        if not finder:
            return
        widget = self._active_widget()
        try:
            start = widget.index("sel.last") if not backward else widget.index("sel.first")
        except tk.TclError:
            start = "insert"
        match = finder.find(start, backward=backward, wrap=True)
        if not match:
            self.msg(f"Não encontrado: {finder.pattern}")
            self.find_panel.set_count("0 ocorrência(s)")
            return
        widget.tag_remove("sel", "1.0", "end")
        widget.tag_add("sel", match.start, match.end)
        widget.mark_set("insert", match.start if backward else match.end)
        widget.see(match.start)
        self.msg(f"Encontrado: {finder.pattern}")

    def replace_one(self) -> None:
        widget = self._active_widget()
        finder = self._finder()
        if not widget or not finder:
            return
        sel = self._sel(widget)
        replacement = self.find_panel.repl_var.get()
        if sel and widget.get(*sel) and self._selection_matches(widget, sel, finder):
            self._push_history()
            widget.delete(*sel)
            widget.insert(sel[0], replacement)
            self._after_edit()
            self._step(False)
            return
        self._step(False)

    def _selection_matches(self, widget, sel, finder: MatchFinder) -> bool:
        text = widget.get(*sel)
        if finder.case:
            return text == finder.pattern
        return text.lower() == finder.pattern.lower()

    def replace_everything(self) -> None:
        widget = self._active_widget()
        pattern = self.find_panel.find_var.get()
        if not widget or not pattern:
            return
        opts = self.find_panel.options()
        self._push_history()
        total = replace_all(widget, pattern, self.find_panel.repl_var.get(), **opts)
        self._after_edit()
        self.update_find_count()
        self.msg(f"{total} ocorrência(s) substituída(s).")

    def _after_edit(self) -> None:
        if self.mode == "design":
            self._touch_design()
        else:
            self.design_stale = True
            self.dirty = True
            self.update_title()
        self.update_status()

    # ============================================================= arquivos
    def check_save(self) -> bool:
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(APP, "Deseja salvar as alterações desta página?",
                                           parent=self)
        if answer is None:
            return False
        if answer:
            return bool(self.save())
        return True

    def set_document(self, code: str, encoding: str = "utf-8", bom: bool = False) -> None:
        c = self.code
        c.delete("1.0", "end")
        c.insert("1.0", code)
        c.edit_reset()
        c.edit_modified(False)
        self.encoding = encoding
        self.bom = bom
        self.design_mod = False
        self.design_stale = True
        self._lossy_warned = False
        self.highlight()
        if self.mode == "design":
            self.load_design(code)
        elif self.mode == "preview":
            self.render_preview()

    def new_file(self, initial: bool = False) -> None:
        if not initial and not self.check_save():
            return
        if not initial:
            self.untitled += 1
        self.path = None
        self.signature = None
        self.set_document(new_page(f"Nova Página {self.untitled}"))
        self.dirty = False
        self.update_title()
        self.update_status()
        self.msg("Nova página criada.")

    def open_file(self, path: Optional[str] = None) -> bool:
        if not isinstance(path, str):
            path = None
        if not self.check_save():
            return False
        if not path:
            path = filedialog.askopenfilename(filetypes=OPEN_FILETYPES, parent=self)
        if not path:
            return False
        try:
            doc = read_document(path)
        except OSError as ex:
            messagebox.showerror(APP, f"Não foi possível abrir:\n{ex}", parent=self)
            return False
        self.path = path
        self.signature = file_stat_signature(path)
        if os.path.splitext(path)[1].lower() not in HTML_EXTS and self.mode != "code":
            self.set_mode("code")
        self.set_document(doc.text, doc.encoding, doc.bom)
        self.dirty = False
        self.settings.add_recent(path)
        self.settings.save()
        self._build_recent_menu()
        self.update_title()
        self.msg(f"Aberto: {path}  ({doc.encoding})")
        if not self.folder.root_dir or not os.path.abspath(path).startswith(
                os.path.abspath(self.folder.root_dir)):
            self.folder.set_root(os.path.dirname(os.path.abspath(path)))
            self.settings.root_dir = self.folder.root_dir
        self.folder.select_path(path)
        return True

    def save(self) -> bool:
        if not self.path:
            return self.save_as()
        return self._write(self.path)

    def save_as(self) -> bool:
        path = filedialog.asksaveasfilename(
            defaultextension=".htm", filetypes=SAVE_FILETYPES, parent=self,
            initialfile=os.path.basename(self.path) if self.path else f"pagina{self.untitled}.htm")
        if not path:
            return False
        self.path = path
        ok = self._write(path)
        if ok:
            self.folder.set_root(os.path.dirname(os.path.abspath(path)))
            self.settings.root_dir = self.folder.root_dir
            self.settings.add_recent(path)
            self.settings.save()
            self._build_recent_menu()
        return ok

    def save_copy(self) -> bool:
        path = filedialog.asksaveasfilename(defaultextension=".htm", filetypes=SAVE_FILETYPES,
                                            parent=self, title="Salvar cópia")
        if not path:
            return False
        html = self.get_html()
        try:
            write_text(path, html, "utf-8")
        except OSError as ex:
            messagebox.showerror(APP, f"Erro ao salvar:\n{ex}", parent=self)
            return False
        self.msg(f"Cópia salva: {path}")
        return True

    def _write(self, path: str) -> bool:
        html = self.get_html()
        try:
            used, promoted = write_text(path, html, self.encoding, self.bom)
        except OSError as ex:
            messagebox.showerror(APP, f"Erro ao salvar:\n{ex}", parent=self)
            self._emergency_autosave()
            return False
        self.encoding = used
        self.dirty = False
        self.signature = file_stat_signature(path)
        self._drop_autosave()
        if promoted:
            self.msg(f"Salvo como UTF-8 (a codificação anterior não comportava o texto): {path}")
        else:
            self.msg(f"Salvo: {path}")
        self.update_title()
        self.update_status()
        return True

    def open_folder(self) -> None:
        folder = filedialog.askdirectory(title="Abrir pasta do site", parent=self)
        if folder:
            self.folder.set_root(folder)
            self.settings.root_dir = self.folder.root_dir
            self.settings.save()
            self.msg(f"Pasta do site: {folder}")

    def reveal(self, path: str) -> None:
        folder = path if os.path.isdir(path) else os.path.dirname(path)
        if not folder:
            return
        try:
            if sys.platform == "win32":
                os.startfile(folder)  # type: ignore[attr-defined]  # noqa: S606
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder])
            else:
                subprocess.Popen(["xdg-open", folder])
        except Exception as ex:  # pragma: no cover - ambiente sem shell gráfico
            self.msg(f"Não foi possível abrir a pasta: {ex}")

    def reveal_current(self) -> None:
        self.reveal(self.path or self.folder.root_dir or os.getcwd())

    def preview_browser(self) -> None:
        if self.dirty or not self.path:
            if not messagebox.askyesno(APP, "Salvar a página para visualizar no navegador?",
                                       parent=self):
                return
            if not self.save():
                return
        try:
            webbrowser.open(pathlib.Path(self.path).resolve().as_uri())
            self.msg("Aberto no navegador.")
        except Exception as ex:  # pragma: no cover
            messagebox.showerror(APP, f"Não foi possível abrir o navegador:\n{ex}", parent=self)

    # ------------------------------------------------------ autosave/recuperação
    def _toggle_autosave(self) -> None:
        self.settings.autosave = bool(self.var_autosave.get())
        self.settings.save()
        self.msg("Recuperação automática " + ("ativada." if self.settings.autosave else "desativada."))

    def _toggle_watch(self) -> None:
        self.settings.watch_file = bool(self.var_watch.get())
        self.settings.save()

    def _schedule_autosave(self) -> None:
        minutes = max(1, int(self.settings.autosave_minutes or 2))
        self._autosave_job = self.after(minutes * 60 * 1000, self._autosave_tick)

    def _autosave_tick(self) -> None:
        if self.settings.autosave and self.dirty:
            self._emergency_autosave(silent=True)
        self._schedule_autosave()

    def _autosave_file(self):
        return autosave_path(self.path, self._page_title())

    def _emergency_autosave(self, silent: bool = False) -> None:
        try:
            target = self._autosave_file()
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(self.get_html())
            if not silent:
                self.msg(f"Cópia de segurança gravada em {target}")
        except OSError as ex:  # pragma: no cover
            if not silent:
                self.msg(f"Falha na cópia de segurança: {ex}")

    def _drop_autosave(self) -> None:
        try:
            target = self._autosave_file()
            if target.exists():
                target.unlink()
        except OSError:  # pragma: no cover
            pass

    def offer_recovery(self) -> None:
        found = find_autosaves()
        if not found:
            return
        path, when = found[0]
        when_text = time.strftime("%d/%m/%Y %H:%M", time.localtime(when))
        if not messagebox.askyesno(
                APP, f"Foi encontrada uma cópia de recuperação de:\n\n{path.name}\n"
                     f"gravada em {when_text}.\n\nDeseja abri-la?", parent=self):
            return
        try:
            doc = read_document(str(path))
        except OSError as ex:
            messagebox.showerror(APP, f"Não foi possível ler a cópia:\n{ex}", parent=self)
            return
        self.path = None
        self.set_document(doc.text, doc.encoding, doc.bom)
        self.dirty = True
        self.update_title()
        self.msg("Cópia de recuperação carregada — salve com um nome.")

    # ------------------------------------------------------ edição externa
    def _schedule_watch(self) -> None:
        self._watch_job = self.after(WATCH_MS, self._watch_tick)

    def _watch_tick(self) -> None:
        try:
            if self.settings.watch_file and self.path and not self._watch_paused:
                current = file_stat_signature(self.path)
                if current and self.signature and current != self.signature:
                    self.signature = current
                    self._external_change()
        finally:
            self._schedule_watch()

    def _external_change(self) -> None:
        self._watch_paused = True
        try:
            if not messagebox.askyesno(
                    APP, "Este arquivo foi modificado por outro programa.\n\n"
                         "Deseja recarregá-lo? (as alterações não salvas serão perdidas)",
                    parent=self):
                return
            try:
                doc = read_document(self.path)
            except OSError as ex:
                messagebox.showerror(APP, f"Não foi possível reler:\n{ex}", parent=self)
                return
            self.set_document(doc.text, doc.encoding, doc.bom)
            self.dirty = False
            self.update_title()
            self.msg("Arquivo recarregado.")
        finally:
            self._watch_paused = False

    # ========================================================= propriedades
    def page_props(self) -> None:
        code = self.get_html()
        lang_match = re.search(r"<html[^>]*\blang\s*=\s*[\"']([^\"']+)", code, re.I)
        values = {
            "title": get_title(code),
            "desc": get_meta(code, "description"),
            "kw": get_meta(code, "keywords"),
            "lang": lang_match.group(1) if lang_match else "pt-br",
            "bgcolor": self._body_attr("bgcolor"),
            "text": self._body_attr("text"),
            "link": self._body_attr("link"),
        }
        dialog = PagePropertiesDialog(self, values, on_color=self._ask_color)
        self.wait_window(dialog)
        data = dialog.result
        if data is None:
            return
        new_code = code
        if data["title"]:
            new_code = set_title(new_code, data["title"])
        if data["desc"]:
            new_code = set_meta(new_code, "description", data["desc"])
        if data["kw"]:
            new_code = set_meta(new_code, "keywords", data["kw"])
        if data["lang"]:
            new_code = re.sub(r"(<html[^>]*\blang\s*=\s*[\"'])[^\"']+",
                              lambda m: m.group(1) + data["lang"], new_code, count=1, flags=re.I)
        if data["bgcolor"] or data["text"] or data["link"]:
            new_code = set_body_attrs(new_code, data["bgcolor"], data["text"], data["link"])
        if new_code != code:
            self.code.delete("1.0", "end")
            self.code.insert("1.0", new_code)
            self.highlight()
            self.dirty = True
            self.design_stale = self.mode != "design"
            self.update_title()
            self.msg("Propriedades da página atualizadas.")

    def _body_attr(self, name: str) -> str:
        m = re.search(r"<body[^>]*\b%s\s*=\s*[\"']([^\"']*)" % name,
                      self.code.get("1.0", "end-1c"), re.I)
        return m.group(1) if m else ""

    # ========================================================== edição básica
    def ev(self, name: str) -> None:
        widget = self._active_widget()
        if widget:
            widget.event_generate(name)

    def select_all(self) -> None:
        widget = self._active_widget()
        if widget:
            widget.tag_add("sel", "1.0", "end-1c")
            return "break"
        return None

    # ================================================================ ajuda
    def shortcuts(self) -> None:
        ReportDialog(self, "Atalhos de teclado", """\
Arquivo
  Ctrl+N  Nova página            Ctrl+O  Abrir
  Ctrl+S  Salvar                 F12     Visualizar no navegador

Editar
  Ctrl+Z  Desfazer               Ctrl+Y  Refazer
  Ctrl+X / Ctrl+C / Ctrl+V  Recortar, copiar, colar
  Ctrl+A  Selecionar tudo
  Ctrl+F  Localizar              Ctrl+H  Substituir
  F3      Próxima ocorrência     Shift+F3  Ocorrência anterior

Modos
  Ctrl+1  Design                 Ctrl+2  Código
  Ctrl+3  Visualizar             F5      Atualizar

Formatação (Design)
  Ctrl+B  Negrito                Ctrl+I  Itálico
  Ctrl+U  Sublinhado             Ctrl+K  Hyperlink

Dica: no modo Design, blocos como tabelas e formulários aparecem como uma
linha cinza "conteúdo protegido" e voltam intactos ao arquivo.""")

    def about(self) -> None:
        messagebox.showinfo(
            "Sobre", f"{APP} {VERSION}\n\n"
                     "Editor de páginas HTML no estilo do antigo FrontPage.\n\n"
                     f"Python {sys.version.split()[0]}\n"
                     f"Visualização embutida: {'ativa' if HAS_WEB else 'indisponível (Ferramentas ▸ Instalar)'}\n\n"
                     "Blocos avançados (tabelas, formulários, scripts) são preservados\n"
                     "mesmo quando a página é editada no modo Design.", parent=self)

    def install_web(self) -> None:
        if HAS_WEB:
            messagebox.showinfo(APP, "A visualização embutida já está instalada.", parent=self)
            return
        if not messagebox.askyesno(
                APP, "Instalar o pacote opcional 'tkinterweb' (visualização embutida)?\n\n"
                     "O download é feito pelo pip e leva alguns instantes.", parent=self):
            return
        self.msg("Instalando tkinterweb...")
        self._pip_run([sys.executable, "-m", "pip", "install", "tkinterweb"])

    def _pip_run(self, cmd: List[str]) -> None:
        def worker():
            try:
                proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                out = (proc.stdout or "") + (proc.stderr or "")
            except Exception as ex:  # pragma: no cover
                proc, out = None, str(ex)
            self.after(0, lambda: self._pip_done(proc, out))

        threading.Thread(target=worker, daemon=True).start()

    def _pip_done(self, proc, output: str) -> None:
        global HAS_WEB, HtmlFrame
        ok = proc is not None and getattr(proc, "returncode", 1) == 0
        if ok:
            try:
                from tkinterweb import HtmlFrame as frame
                HtmlFrame = frame
                HAS_WEB = True
                self._build_preview()
                if self.mode == "preview":
                    self.render_preview()
                self.msg("tkinterweb instalado — visualização embutida ativa.")
                return
            except Exception as ex:  # pragma: no cover
                output = str(ex)
                ok = False
        self.msg("Não foi possível instalar o tkinterweb.")
        ReportDialog(self, "Instalação do tkinterweb", output[-4000:] or "(sem saída)")

    # ================================================================= sair
    def quit_app(self) -> None:
        if not self.check_save():
            return
        if not self.dirty:
            self._drop_autosave()
        try:
            self.settings.mode = self.mode
            if self.folder.root_dir:
                self.settings.root_dir = self.folder.root_dir
            self.settings.geometry = self.geometry()
            self.settings.save()
        except tk.TclError:  # pragma: no cover
            pass
        self.destroy()


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # pragma: no cover - stdout sem reconfigure
        pass
    path = next((a for a in argv if not a.startswith("-")), None)
    app = App(path)
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
