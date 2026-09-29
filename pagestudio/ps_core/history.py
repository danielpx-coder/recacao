# -*- coding: utf-8 -*-
"""
Desfazer/Refazer confiável para o modo Design.

O widget ``tkinter.Text`` só desfaz *digitação*: as formatações aplicadas por
tags (negrito, título, cor, lista...) eram invisíveis para o Ctrl+Z, e o
resultado era um editor em que "desfazer" parecia aleatório.

Aqui o histórico guarda fotos completas do documento — texto **e** faixas de
tags — e o Ctrl+Z/Ctrl+Y do modo Design passa por esta pilha. O histórico é
limitado a ``limit`` estados para não crescer indefinidamente.
"""

from __future__ import annotations

from typing import List, Optional, Sequence, Tuple

State = Tuple[str, Tuple[Tuple[str, Tuple[str, str]], ...]]

#: Tags que o modo Design usa e que, portanto, entram na foto.
DESIGN_TAGS = ("bold", "italic", "bi", "underline", "h1", "h2", "h3", "pre",
               "li", "hr", "center", "right")


class DesignHistory:
    """Pilha de desfazer/refazer baseada em fotos do documento."""

    def __init__(self, doc, limit: int = 60):
        self.doc = doc
        self.limit = max(2, int(limit))
        self._undo: List[State] = []
        self._redo: List[State] = []

    # -- introspecção -------------------------------------------------------
    def can_undo(self) -> bool:
        return bool(self._undo)

    def can_redo(self) -> bool:
        return bool(self._redo)

    def __len__(self) -> int:
        return len(self._undo)

    def clear(self) -> None:
        self._undo.clear()
        self._redo.clear()

    # -- captura / restauração ---------------------------------------------
    def capture(self) -> State:
        """Fotografa o estado atual do documento."""
        text = self.doc.get("1.0", "end-1c")
        ranges: List[Tuple[str, Tuple[str, str]]] = []
        for tag in self._tag_names():
            r = self.doc.tag_ranges(tag)
            if not r:
                continue
            pairs = tuple((str(r[i]), str(r[i + 1])) for i in range(0, len(r), 2))
            ranges.append((tag, pairs))
        return text, tuple(ranges)

    def apply(self, state: State) -> None:
        """Restaura uma foto no documento."""
        text, ranges = state
        doc = self.doc
        undo_state = None
        try:
            undo_state = doc.cget("undo")
            doc.configure(undo=False)
        except Exception:  # documento sem opção "undo" (str, testes)
            pass
        try:
            doc.delete("1.0", "end")
            doc.insert("1.0", text)
            for tag, pairs in ranges:
                for start, end in pairs:
                    doc.tag_add(tag, start, end)
        finally:
            if undo_state is not None:
                try:
                    doc.configure(undo=undo_state)
                except Exception:  # pragma: no cover - defensivo
                    pass

    # -- operações ----------------------------------------------------------
    def push(self, state: Optional[State] = None) -> None:
        """Registra o estado *anterior* a uma edição (chame antes de editar)."""
        self._undo.append(state if state is not None else self.capture())
        if len(self._undo) > self.limit:
            del self._undo[0]
        self._redo.clear()

    def undo(self) -> Optional[State]:
        """Volta um passo e devolve o estado atual (para entrar no refazer)."""
        if not self._undo:
            return None
        current = self.capture()
        state = self._undo.pop()
        self._redo.append(current)
        self.apply(state)
        return state

    def redo(self) -> Optional[State]:
        """Avança um passo e devolve o estado restaurado."""
        if not self._redo:
            return None
        current = self.capture()
        state = self._redo.pop()
        self._undo.append(current)
        self.apply(state)
        return state

    # -- interno ------------------------------------------------------------
    def _tag_names(self) -> Sequence[str]:
        try:
            names = set(self.doc.tag_names())
        except Exception:  # pragma: no cover - defensivo
            return DESIGN_TAGS
        wanted = {t for t in names if t in DESIGN_TAGS or t.startswith(("a:", "c:", "img:", "pb:", "s:"))}
        return sorted(wanted)
