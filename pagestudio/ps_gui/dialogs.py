# -*- coding: utf-8 -*-
"""Diálogos do RD5 PageStudio (Propriedades da página, Inserir tabela...)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from ps_core.consts import APP, FACE, FONT, FONT_S


class _Modal(tk.Toplevel):
    """Base para diálogos modais com OK/Cancelar e Enter/Esc."""

    def __init__(self, parent, title, width=470):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=FACE)
        self.resizable(False, False)
        self.transient(parent)
        self.result = None
        self._body = tk.Frame(self, bg=FACE)
        self._body.pack(fill="both", expand=True, padx=10, pady=(10, 4))
        bar = tk.Frame(self, bg=FACE)
        bar.pack(fill="x", padx=10, pady=(4, 10))
        ok = tk.Button(bar, text="OK", width=9, command=self._ok, default="active", font=FONT)
        ok.pack(side="right", padx=(6, 0))
        tk.Button(bar, text="Cancelar", width=9, command=self.destroy, font=FONT).pack(side="right")
        self.bind("<Return>", lambda _e: self._ok())
        self.bind("<Escape>", lambda _e: self.destroy())
        self._width = width
        self.after_idle(self._place)

    def _place(self):
        self.update_idletasks()
        try:
            self.grab_set()
            px = self.master.winfo_rootx() + max(0, (self.master.winfo_width() - self.winfo_width()) // 2)
            py = self.master.winfo_rooty() + max(0, (self.master.winfo_height() - self.winfo_height()) // 3)
            self.geometry(f"+{px}+{py}")
        except tk.TclError:  # pragma: no cover
            pass
        self.focus_set()

    def _ok(self):
        self.result = self.collect()
        if self.result is not None:
            self.destroy()

    # a implementar pelas subclasses
    def collect(self):  # pragma: no cover - interface
        raise NotImplementedError


class PagePropertiesDialog(_Modal):
    """Título, descrição, palavras-chave, idioma e cores da página."""

    def __init__(self, parent, values: dict, on_color=None):
        self.v = values
        self._on_color = on_color
        super().__init__(parent, "Propriedades da página", width=500)
        self._build()

    def _build(self):
        b = self._body
        rows = [("Título da página:", "title"), ("Descrição (meta):", "desc"),
                ("Palavras-chave:", "kw")]
        self.entries = {}
        self.widgets = {}
        for i, (label, key) in enumerate(rows):
            tk.Label(b, text=label, bg=FACE, font=FONT, anchor="w").grid(
                row=i, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=self.v.get(key, ""))
            ent = tk.Entry(b, textvariable=var, font=FONT, width=46,
                           relief="solid", bd=1)
            ent.grid(row=i, column=1, columnspan=3, sticky="we", pady=3, padx=(6, 0))
            self.entries[key] = var
            self.widgets[key] = ent
        self.widgets["title"].focus_set()

        tk.Label(b, text="Idioma:", bg=FACE, font=FONT).grid(row=3, column=0, sticky="w", pady=3)
        self.lang = tk.StringVar(value=self.v.get("lang", "pt-br"))
        ttk.Combobox(b, textvariable=self.lang, font=FONT, width=10, state="readonly",
                     values=("pt-br", "pt-pt", "en", "es", "fr", "it", "de")).grid(
            row=3, column=1, sticky="w", pady=3, padx=(6, 0))

        self.bg_var = tk.StringVar(value=self.v.get("bgcolor", ""))
        self.txt_var = tk.StringVar(value=self.v.get("text", ""))
        self.link_var = tk.StringVar(value=self.v.get("link", ""))
        for col, (label, var) in enumerate((("Fundo:", self.bg_var),
                                            ("Texto:", self.txt_var),
                                            ("Links:", self.link_var))):
            tk.Label(b, text=label, bg=FACE, font=FONT).grid(row=4, column=col * 1, sticky="e",
                                                             padx=(0 if col == 0 else 8, 0), pady=3)
            tk.Button(b, textvariable=var, width=9, font=FONT_S, relief="solid", bd=1,
                      command=lambda v=var: self._pick(v)).grid(row=4, column=col + 1,
                                                                sticky="w", padx=(2, 0), pady=3)
        b.columnconfigure(1, weight=1)

        tk.Label(b, bg=FACE, fg="#404040", font=FONT_S, justify="left",
                 text="Deixe uma cor vazia para não alterar o atributo correspondente.").grid(
            row=5, column=0, columnspan=4, sticky="w", pady=(8, 0))

    def _pick(self, var):
        if not self._on_color:  # pragma: no cover - sempre fornecido pelo app
            return
        color = self._on_color(var.get())
        if color:
            var.set(color)

    def collect(self):
        return {
            "title": self.entries["title"].get().strip(),
            "desc": self.entries["desc"].get().strip(),
            "kw": self.entries["kw"].get().strip(),
            "lang": self.lang.get().strip(),
            "bgcolor": self.bg_var.get().strip(),
            "text": self.txt_var.get().strip(),
            "link": self.link_var.get().strip(),
        }


class TableDialog(_Modal):
    """Inserir tabela: linhas, colunas, borda, largura e cabeçalho."""

    def __init__(self, parent):
        super().__init__(parent, "Inserir tabela", width=420)
        self._build()

    def _build(self):
        b = self._body
        self.rows = tk.StringVar(value="3")
        self.cols = tk.StringVar(value="3")
        self.border = tk.StringVar(value="1")
        self.pad = tk.StringVar(value="4")
        self.width = tk.StringVar(value="100%")
        self.header = tk.BooleanVar(value=True)
        specs = [("Linhas:", self.rows), ("Colunas:", self.cols),
                 ("Borda:", self.border), ("Espaço interno:", self.pad),
                 ("Largura:", self.width)]
        for i, (label, var) in enumerate(specs):
            r, c = divmod(i, 2)
            tk.Label(b, text=label, bg=FACE, font=FONT).grid(row=r, column=c * 2, sticky="e",
                                                             padx=(0, 4), pady=4)
            tk.Entry(b, textvariable=var, width=9, font=FONT, relief="solid", bd=1).grid(
                row=r, column=c * 2 + 1, sticky="w", pady=4, padx=(0, 14))
        self.header_chk = tk.Checkbutton(b, text="Primeira linha é cabeçalho",
                                         variable=self.header, bg=FACE, font=FONT)
        self.header_chk.grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))

    def collect(self):
        def num(var, default, minimum=0):
            try:
                return max(minimum, int(str(var.get()).strip()))
            except ValueError:
                return default
        return {
            "rows": num(self.rows, 3, 1),
            "cols": num(self.cols, 3, 1),
            "border": num(self.border, 1, 0),
            "padding": num(self.pad, 4, 0),
            "width": self.width.get().strip() or "100%",
            "header": bool(self.header.get()),
        }


class LinkDialog(_Modal):
    """Inserir hyperlink: endereço e texto (opcional)."""

    def __init__(self, parent, url: str = "https://", text: str = ""):
        self._url = url
        self._text = text
        super().__init__(parent, "Inserir hyperlink", width=470)
        self._build()

    def _build(self):
        b = self._body
        tk.Label(b, text="Endereço (URL):", bg=FACE, font=FONT).grid(row=0, column=0, sticky="w", pady=4)
        self.url = tk.StringVar(value=self._url)
        tk.Entry(b, textvariable=self.url, width=44, font=FONT, relief="solid", bd=1).grid(
            row=0, column=1, sticky="we", pady=4, padx=(6, 0))
        tk.Label(b, text="Texto exibido:", bg=FACE, font=FONT).grid(row=1, column=0, sticky="w", pady=4)
        self.text = tk.StringVar(value=self._text)
        tk.Entry(b, textvariable=self.text, width=44, font=FONT, relief="solid", bd=1).grid(
            row=1, column=1, sticky="we", pady=4, padx=(6, 0))
        b.columnconfigure(1, weight=1)
        tk.Label(b, bg=FACE, fg="#404040", font=FONT_S, justify="left",
                 text="Deixe o texto vazio para usar o próprio endereço.").grid(
            row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))

    def collect(self):
        url = self.url.get().strip()
        if not url:
            return None
        return {"url": url, "text": self.text.get().strip()}


class ReportDialog(tk.Toplevel):
    """Janela de texto somente leitura (relatórios de validação, contagem...)."""

    def __init__(self, parent, title: str, text: str):
        super().__init__(parent)
        self.title(f"{title} — {APP}")
        self.configure(bg=FACE)
        self.geometry("620x380")
        self.transient(parent)
        frame = tk.Frame(self, bg="white", bd=2, relief="sunken")
        frame.pack(fill="both", expand=True, padx=8, pady=8)
        widget = tk.Text(frame, wrap="word", font=FONT, bg="white", relief="flat",
                         padx=8, pady=6)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=widget.yview)
        widget.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        widget.pack(side="left", fill="both", expand=True)
        widget.insert("1.0", text)
        widget.configure(state="disabled")
        tk.Button(self, text="Fechar", command=self.destroy, width=10, font=FONT).pack(pady=(0, 8))
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after_idle(self.focus_set)
