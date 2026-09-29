# -*- coding: utf-8 -*-
"""Peças reaproveitáveis da interface."""

from __future__ import annotations

import tkinter as tk

from ps_core.consts import FONT_S, YELLOW


class Tip:
    """Dica amarela clássica, mostrada após um pequeno atraso."""

    def __init__(self, widget, text, delay=420):
        self.w = widget
        self.t = text
        self.delay = delay
        self.tw = None
        self._job = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<ButtonPress>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def _schedule(self, _event=None):
        self.hide()
        try:
            self._job = self.w.after(self.delay, self.show)
        except tk.TclError:  # pragma: no cover - widget já destruído
            self._job = None

    def show(self, _event=None):
        self._job = None
        if self.tw or not self.t:
            return
        try:
            if not self.w.winfo_ismapped():
                return
            self.tw = tk.Toplevel(self.w)
            self.tw.wm_overrideredirect(True)
            x = self.w.winfo_rootx() + 8
            y = self.w.winfo_rooty() + self.w.winfo_height() + 4
            self.tw.wm_geometry(f"+{x}+{y}")
            tk.Label(self.tw, text=self.t, bg=YELLOW, fg="black", relief="solid",
                     bd=1, font=FONT_S, padx=4, pady=1).pack()
        except tk.TclError:  # pragma: no cover - corrida com destruição
            self.tw = None

    def hide(self, _event=None):
        if self._job:
            try:
                self.w.after_cancel(self._job)
            except tk.TclError:  # pragma: no cover
                pass
            self._job = None
        if self.tw:
            try:
                self.tw.destroy()
            except tk.TclError:  # pragma: no cover
                pass
            self.tw = None
