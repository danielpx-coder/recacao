# -*- coding: utf-8 -*-
"""Painéis laterais e de busca do RD5 PageStudio."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Callable, Dict, List, Optional

from ps_core.consts import FACE, FONT, FONT_S, NAVY
from ps_gui.widgets import Tip

MAX_HITS = 400          # limite de arquivos mostrados pelo filtro
MAX_DEPTH = 8           # profundidade máxima da varredura do filtro


class FolderPanel(tk.Frame):
    """Lista de Pastas: árvore do site, filtro por nome e menu de contexto."""

    def __init__(self, master, on_open: Callable[[str], None],
                 on_reveal: Callable[[str], None]):
        super().__init__(master, bg=FACE, bd=2, relief="sunken")
        self.on_open = on_open
        self.on_reveal = on_reveal
        self.root_dir: Optional[str] = None
        self.node_path: Dict[str, str] = {}
        self._filter_job = None

        head = tk.Frame(self, bg=NAVY)
        head.pack(fill="x")
        tk.Label(head, text="Lista de Pastas", bg=NAVY, fg="white",
                 font=("Tahoma", 8, "bold"), anchor="w").pack(side="left", padx=4, pady=1)
        btn = tk.Button(head, text="\u21bb", command=self.refresh, bg=NAVY, fg="white",
                        relief="flat", bd=0, font=FONT_S, takefocus=0,
                        activebackground=NAVY, activeforeground="white")
        btn.pack(side="right", padx=2)
        Tip(btn, "Atualizar a lista (F5)")

        filt = tk.Frame(self, bg=FACE)
        filt.pack(fill="x")
        tk.Label(filt, text="Filtrar:", bg=FACE, font=FONT_S).pack(side="left", padx=(4, 2))
        self.filter_var = tk.StringVar()
        ent = tk.Entry(filt, textvariable=self.filter_var, font=FONT_S, relief="solid", bd=1)
        ent.pack(side="left", fill="x", expand=True, padx=(0, 4), pady=2)
        ent.bind("<KeyRelease>", self._filter_typed)
        ent.bind("<Escape>", lambda _e: (self.filter_var.set(""), self.build(self.root_dir)))

        body = tk.Frame(self, bg="white")
        body.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(body, show="tree", selectmode="browse")
        ys = ttk.Scrollbar(body, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=ys.set)
        ys.pack(side="right", fill="y")
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<<TreeviewOpen>>", self._on_open_node)
        self.tree.bind("<Double-1>", self._on_double)
        self.tree.bind("<Return>", self._on_double)
        self.tree.bind("<Button-3>", self._popup)

        self.menu = tk.Menu(self, tearoff=0)
        self.menu.add_command(label="Abrir", command=self._ctx_open)
        self.menu.add_command(label="Abrir pasta no sistema", command=self._ctx_reveal)
        self.menu.add_separator()
        self.menu.add_command(label="Nova página aqui...", command=self._ctx_new_file)
        self.menu.add_command(label="Nova pasta aqui...", command=self._ctx_new_folder)
        self.menu.add_separator()
        self.menu.add_command(label="Renomear...", command=self._ctx_rename)
        self.menu.add_command(label="Excluir", command=self._ctx_delete)
        self.menu.add_separator()
        self.menu.add_command(label="Atualizar", command=self.refresh)

    # ------------------------------------------------------------- árvore
    def set_root(self, folder: Optional[str]) -> None:
        if not folder:
            return
        self.root_dir = os.path.abspath(folder)
        self.filter_var.set("")
        self.build(self.root_dir)

    def build(self, folder: Optional[str]) -> None:
        """(Re)constrói a árvore a partir de ``folder``."""
        self.tree.delete(*self.tree.get_children())
        self.node_path.clear()
        if not folder:
            return
        folder = os.path.abspath(folder)
        self.root_dir = folder
        label = os.path.basename(folder) or folder
        root = self.tree.insert("", "end", text=f"\U0001F4C1 {label}", open=True)
        self.node_path[root] = folder
        self.fill(root, folder)

    def fill(self, parent: str, folder: str) -> None:
        for child in self.tree.get_children(parent):
            self.tree.delete(child)
            self.node_path.pop(child, None)
        try:
            names = sorted(os.listdir(folder),
                           key=lambda n: (not os.path.isdir(os.path.join(folder, n)), n.lower()))
        except OSError:
            return
        for name in names:
            if name.startswith(".") or name in ("__pycache__", "node_modules"):
                continue
            path = os.path.join(folder, name)
            is_dir = os.path.isdir(path)
            icon = "\U0001F4C1 " if is_dir else "\U0001F4C4 "
            iid = self.tree.insert(parent, "end", text=icon + name)
            self.node_path[iid] = path
            if is_dir:
                self.tree.insert(iid, "end", text="\u2026")

    def refresh(self) -> None:
        if self.filter_var.get().strip():
            self._apply_filter(self.filter_var.get().strip())
        else:
            self.build(self.root_dir)
        self.tree.selection_set(())

    def select_path(self, path: str) -> None:
        """Destaca um arquivo na árvore (se ele estiver visível)."""
        for iid, target in self.node_path.items():
            if os.path.abspath(target) == os.path.abspath(path):
                self.tree.see(iid)
                self.tree.selection_set(iid)
                return

    # ------------------------------------------------------------- filtro
    def _filter_typed(self, _event=None) -> None:
        if self._filter_job:
            self.after_cancel(self._filter_job)
        self._filter_job = self.after(250, self._run_filter)

    def _run_filter(self) -> None:
        self._filter_job = None
        text = self.filter_var.get().strip()
        if not text:
            self.build(self.root_dir)
            return
        self._apply_filter(text)

    def _apply_filter(self, needle: str) -> None:
        if not self.root_dir:
            return
        needle = needle.lower()
        self.tree.delete(*self.tree.get_children())
        self.node_path.clear()
        hits: List[str] = []
        base = self.root_dir
        root_depth = base.rstrip(os.sep).count(os.sep)
        for current, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in
                       ("__pycache__", "node_modules", ".git")]
            if current.rstrip(os.sep).count(os.sep) - root_depth > MAX_DEPTH:
                dirs[:] = []
            for name in files:
                if needle in name.lower():
                    hits.append(os.path.join(current, name))
                    if len(hits) >= MAX_HITS:
                        break
            if len(hits) >= MAX_HITS:
                break
        header = self.tree.insert("", "end",
                                  text=f"\U0001F50D {len(hits)} arquivo(s) com \"{needle}\"",
                                  open=True)
        self.node_path[header] = base
        for path in hits:
            rel = os.path.relpath(path, base).replace(os.sep, " \u203a ")
            iid = self.tree.insert(header, "end", text=f"\U0001F4C4 {rel}")
            self.node_path[iid] = path

    # ------------------------------------------------------------- eventos
    def _on_open_node(self, _event=None) -> None:
        iid = self.tree.focus()
        path = self.node_path.get(iid)
        if path and os.path.isdir(path):
            self.fill(iid, path)

    def _on_double(self, _event=None) -> None:
        iid = self.tree.focus()
        path = self.node_path.get(iid)
        if not path:
            return
        if os.path.isfile(path):
            self.on_open(path)
        elif os.path.isdir(path):
            self.fill(iid, path)

    def _popup(self, event) -> None:
        iid = self.tree.identify_row(event.y)
        if not iid:
            return
        self.tree.selection_set(iid)
        self.tree.focus(iid)
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def _selected(self) -> Optional[str]:
        sel = self.tree.selection()
        return self.node_path.get(sel[0]) if sel else None

    def _parent_dir(self, path: str) -> str:
        return path if os.path.isdir(path) else os.path.dirname(path)

    # ---------------------------------------------------------- contexto
    def _ctx_open(self) -> None:
        path = self._selected()
        if path and os.path.isfile(path):
            self.on_open(path)
        elif path:
            self._on_double()

    def _ctx_reveal(self) -> None:
        path = self._selected()
        if path:
            self.on_reveal(path)

    def _ctx_new_file(self) -> None:
        path = self._selected()
        folder = self._parent_dir(path) if path else self.root_dir
        if not folder:
            return
        name = simpledialog.askstring("Nova página", "Nome do arquivo:",
                                      initialvalue="nova_pagina.htm", parent=self)
        if not name:
            return
        target = os.path.join(folder, name)
        if os.path.exists(target):
            messagebox.showwarning("Nova página", "Já existe um arquivo com esse nome.", parent=self)
            return
        try:
            from ps_core.consts import new_page
            with open(target, "w", encoding="utf-8", newline="\n") as fh:
                fh.write(new_page(os.path.splitext(name)[0]))
        except OSError as ex:
            messagebox.showerror("Nova página", f"Não foi possível criar:\n{ex}", parent=self)
            return
        self.refresh()
        self.on_open(target)

    def _ctx_new_folder(self) -> None:
        path = self._selected()
        folder = self._parent_dir(path) if path else self.root_dir
        if not folder:
            return
        name = simpledialog.askstring("Nova pasta", "Nome da pasta:", parent=self)
        if not name:
            return
        try:
            os.makedirs(os.path.join(folder, name), exist_ok=True)
        except OSError as ex:
            messagebox.showerror("Nova pasta", f"Não foi possível criar:\n{ex}", parent=self)
            return
        self.refresh()

    def _ctx_rename(self) -> None:
        path = self._selected()
        if not path:
            return
        name = simpledialog.askstring("Renomear", "Novo nome:",
                                      initialvalue=os.path.basename(path), parent=self)
        if not name or name == os.path.basename(path):
            return
        target = os.path.join(os.path.dirname(path), name)
        if os.path.exists(target):
            messagebox.showwarning("Renomear", "Já existe um item com esse nome.", parent=self)
            return
        try:
            os.rename(path, target)
        except OSError as ex:
            messagebox.showerror("Renomear", str(ex), parent=self)
            return
        self.refresh()

    def _ctx_delete(self) -> None:
        path = self._selected()
        if not path:
            return
        if not messagebox.askyesno("Excluir", f"Excluir definitivamente?\n\n{path}", parent=self):
            return
        try:
            if os.path.isdir(path):
                import shutil
                shutil.rmtree(path)
            else:
                os.remove(path)
        except OSError as ex:
            messagebox.showerror("Excluir", str(ex), parent=self)
            return
        self.refresh()


class FindPanel(tk.Frame):
    """Barra Localizar/Substituir (Ctrl+F / Ctrl+H) com contador de ocorrências."""

    def __init__(self, master, callbacks: dict):
        super().__init__(master, bg=FACE, bd=1, relief="solid")
        self.cb = callbacks
        self.replace_mode = tk.BooleanVar(value=False)

        row1 = tk.Frame(self, bg=FACE)
        row1.pack(fill="x", padx=4, pady=(3, 1))
        tk.Label(row1, text="Localizar:", bg=FACE, font=FONT).pack(side="left")
        self.find_var = tk.StringVar()
        self.find_entry = tk.Entry(row1, textvariable=self.find_var, width=28, font=FONT,
                                   relief="solid", bd=1)
        self.find_entry.pack(side="left", padx=4)
        self.find_entry.bind("<Return>", lambda _e: self.cb["next"]())
        self.find_entry.bind("<Shift-Return>", lambda _e: self.cb["prev"]())
        self.find_entry.bind("<Escape>", lambda _e: self.cb["close"]())
        self.find_entry.bind("<KeyRelease>", lambda _e: self.cb["changed"]())
        self.count = tk.Label(row1, text="", bg=FACE, font=FONT_S, width=18, anchor="w")
        self.count.pack(side="left", padx=4)
        for text, key in (("\u25b2", "prev"), ("\u25bc", "next")):
            b = tk.Button(row1, text=text, width=2, relief="flat", bd=1, bg=FACE,
                          overrelief="raised", takefocus=0, font=FONT,
                          command=self.cb[key])
            b.pack(side="left", padx=1)
            Tip(b, "Ocorrência anterior (Shift+F3)" if key == "prev" else "Próxima ocorrência (F3)")

        row2 = tk.Frame(self, bg=FACE)
        row2.pack(fill="x", padx=4, pady=(0, 3))
        tk.Label(row2, text="Substituir:", bg=FACE, font=FONT).pack(side="left")
        self.repl_var = tk.StringVar()
        self.repl_entry = tk.Entry(row2, textvariable=self.repl_var, width=28, font=FONT,
                                   relief="solid", bd=1)
        self.repl_entry.pack(side="left", padx=4)
        self.repl_entry.bind("<Return>", lambda _e: self.cb["replace"]())
        for text, key, tip in (("Substituir", "replace", "Substituir esta ocorrência"),
                               ("Tudo", "replace_all", "Substituir todas as ocorrências")):
            b = tk.Button(row2, text=text, relief="flat", bd=1, bg=FACE, font=FONT_S,
                          overrelief="raised", takefocus=0, padx=6, command=self.cb[key])
            b.pack(side="left", padx=1)
            Tip(b, tip)

        opts = tk.Frame(row2, bg=FACE)
        opts.pack(side="left", padx=8)
        self.case_var = tk.BooleanVar(value=False)
        self.regex_var = tk.BooleanVar(value=False)
        self.whole_var = tk.BooleanVar(value=False)
        for text, var in (("Aa", self.case_var), ("[.]", self.regex_var), ("ab", self.whole_var)):
            tk.Checkbutton(opts, text=text, variable=var, bg=FACE, font=FONT_S,
                           command=self.cb["changed"]).pack(side="left")
        Tip(opts, "Aa = diferenciar maiúsculas | [.] = expressão regular | ab = palavra inteira")

        close = tk.Button(row1, text="\u2715", width=2, relief="flat", bd=1, bg=FACE,
                          overrelief="raised", takefocus=0, font=FONT, command=self.cb["close"])
        close.pack(side="right", padx=2)
        Tip(close, "Fechar (Esc)")

    # ------------------------------------------------------------- helpers
    def options(self) -> dict:
        return {"case": bool(self.case_var.get()),
                "regex": bool(self.regex_var.get()),
                "whole": bool(self.whole_var.get())}

    def show(self, replace: bool = False, initial: str = "") -> None:
        """Exibe o painel (o empacotamento é feito pelo aplicativo)."""
        self.replace_mode.set(replace)
        if initial:
            self.find_var.set(initial)
        self.repl_entry.configure(state="normal" if replace else "disabled")
        target = self.repl_entry if replace and self.find_var.get() else self.find_entry
        target.focus_set()
        if target is self.find_entry and self.find_var.get():
            target.select_range(0, "end")
        self.cb["changed"]()

    def hide(self) -> None:
        self.pack_forget()

    def set_count(self, text: str) -> None:
        self.count.config(text=text)
