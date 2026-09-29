# -*- coding: utf-8 -*-
"""
Duplicata mínima da API de ``tkinter.Text`` usada pelo RD5 PageStudio.

O modo Design do editor fala com um "documento de texto" que sabe ``get``,
``insert``, ``delete``, ``dump``, ``tag_add``, ``tag_remove``, ``tag_ranges``,
``tag_names``, ``index``, ``compare`` e ``search``. Esta classe implementa esse
contrato com a mesma semântica de índices do Tk (``linha.coluna``, linha base 1
e coluna base 0, ``end-1c`` = fim real do texto, modificadores ``linestart`` e
``lineend``).

Ela existe para que a conversão Design ⇄ HTML, o histórico de desfazer e o motor
de busca sejam testados de verdade, sem display nem Tkinter.
"""

from __future__ import annotations

import re
from typing import Dict, List, Tuple

Index = str

try:  # com Tkinter disponível, usa o erro real do Tk (igual ao aplicativo)
    from tkinter import TclError
except Exception:  # sem Tkinter (testes de núcleo), um erro equivalente
    class TclError(Exception):
        """Equivalente ao tkinter.TclError: índice ou marca inexistente."""

_INDEX_RE = re.compile(
    r"^(?P<base>end-1c|end|insert|current|sel\.first|sel\.last|\d+\.end|\d+\.\d+)"
    r"(?P<rest>.*)$")
_DELTA_RE = re.compile(r"([+-])(\d+)([a-z]+)")


class PlainDoc:
    """Documento de texto com tags, compatível com o Tk para os testes."""

    def __init__(self, text: str = "", undo: bool = True):
        self._text = text
        self._tags: Dict[str, List[List[int]]] = {}
        self._undo = undo
        self._modified = False
        self.marks: Dict[str, int] = {"insert": 0}

    # ------------------------------------------------------------- texto
    def get(self, start: Index = "1.0", end: Index = "end") -> str:
        return self._text[self.off(start):self.off(end)]

    def insert(self, index: Index, text: str, tags=()) -> None:
        pos = self.off(index)
        self._text = self._text[:pos] + text + self._text[pos:]
        shift = len(text)
        for rng in self._tags.values():
            for r in rng:
                if r[0] > pos or (r[0] == pos and shift):
                    r[0] += shift
                if r[1] > pos:
                    r[1] += shift
        if isinstance(tags, str):
            tags = (tags,)
        for t in tags or ():
            self.tag_add(t, self.idx(pos), self.idx(pos + shift))
        self.marks["insert"] = pos + shift
        self._modified = True

    def insert_pieces(self, pieces) -> None:
        """Constrói o documento de uma vez a partir de ``(texto, tags)``.

        Equivale a inserir cada pedaço em sequência no Tk, mas calcula as faixas
        de tags diretamente sobre os deslocamentos (como o editor faz ao carregar
        uma página no modo Design).
        """
        self._text = "".join(txt for txt, _tags in pieces)
        self._tags = {}
        pos = 0
        for txt, tags in pieces:
            if isinstance(tags, str):
                tags = (tags,)
            for t in tags or ():
                self.tag_add(t, self.idx(pos), self.idx(pos + len(txt)))
            pos += len(txt)
        self.marks["insert"] = len(self._text)

    def delete(self, start: Index, end: Index = "end") -> None:
        a, b = self.off(start), min(self.off(end), len(self._text))
        if b <= a:
            return
        self._text = self._text[:a] + self._text[b:]
        for tag, ranges in list(self._tags.items()):
            kept = []
            for s, e in ranges:
                if e <= a or s >= b:
                    kept.append([s, e])
                    continue
                ns, ne = s, e
                if s >= a:
                    ns = a
                if e > b:
                    ne = a + (e - b)
                elif e > a:
                    ne = a
                if ne > ns:
                    kept.append([ns, ne])
            if kept:
                self._tags[tag] = kept
            else:
                self._tags.pop(tag, None)
        self.marks["insert"] = a
        self._modified = True

    def index(self, index: Index) -> Index:
        return self.idx(self.off(index))

    def compare(self, a: Index, op: str, b: Index) -> bool:
        x, y = self.off(a), self.off(b)
        return {"<": x < y, "<=": x <= y, ">": x > y, ">=": x >= y,
                "==": x == y, "!=": x != y}[op]

    # ------------------------------------------------- conversão de índices
    def off(self, index) -> int:
        """Converte índice do Tk em deslocamento de caracteres."""
        if isinstance(index, int):
            return max(0, min(index, len(self._text)))
        if isinstance(index, (list, tuple)):  # pragma: no cover - não usado
            return self.off(index[0])

        m = _INDEX_RE.match(str(index).strip())
        if not m:
            raise ValueError(f"índice inválido: {index!r}")
        base, rest = m.group("base"), m.group("rest")

        pos = self._base_off(base)
        for sign, num, unit in _DELTA_RE.findall(rest):
            step = int(num) * (1 if unit.startswith("c") else 1)
            pos += step if sign == "+" else -step
        for word in re.findall(r"[a-z]+", _DELTA_RE.sub("", rest)):
            pos = self._apply_modifier(pos, word)
        return max(0, min(pos, len(self._text)))

    def _base_off(self, base: str) -> int:
        if base == "end":
            return len(self._text) + 1        # o Tk conta a quebra fantasma
        if base == "end-1c":
            return len(self._text)
        if base in ("insert", "current"):
            return self.marks.get("insert", 0)
        if base in ("sel.first", "sel.last"):
            ranges = self._tags.get("sel")
            if not ranges:
                # O Tk levanta TclError quando não há seleção.
                raise TclError("sem seleção: " + base)
            return ranges[0][0 if base.endswith("first") else 1]
        line, _, col = base.partition(".")
        if col == "end":
            lines = self._text.split("\n")
            ln = max(1, int(line))
            at = sum(len(l) + 1 for l in lines[:ln - 1])
            return at + len(lines[ln - 1]) if ln - 1 < len(lines) else len(self._text)
        lines = self._text.split("\n")
        ln = max(1, int(line))
        return sum(len(l) + 1 for l in lines[:ln - 1]) + max(0, int(col or 0))

    def _apply_modifier(self, pos: int, word: str) -> int:
        if word == "linestart":
            return self._text.rfind("\n", 0, pos) + 1
        if word == "lineend":
            nxt = self._text.find("\n", pos)
            return len(self._text) if nxt < 0 else nxt
        return pos

    def idx(self, pos: int) -> Index:
        """Converte deslocamento em índice do Tk."""
        pos = max(0, min(pos, len(self._text)))
        head = self._text[:pos]
        return f"{head.count(chr(10)) + 1}.{pos - (head.rfind(chr(10)) + 1)}"

    # ---------------------------------------------------------------- tags
    def tag_add(self, tag: str, start: Index, end: Index) -> None:
        a, b = self.off(start), self.off(end)
        if b <= a:
            return
        ranges = self._tags.setdefault(tag, [])
        for r in ranges:
            if r[0] <= b and a <= r[1]:      # sobrepõe ou encosta: funde
                r[0], r[1] = min(r[0], a), max(r[1], b)
                ranges.sort()
                return
        ranges.append([a, b])
        ranges.sort()

    def tag_remove(self, tag: str, start: Index = "1.0", end: Index = "end") -> None:
        a, b = self.off(start), self.off(end)
        ranges = self._tags.get(tag)
        if not ranges:
            return
        kept = []
        for s, e in ranges:
            if e <= a or s >= b:
                kept.append([s, e])
                continue
            if s < a:
                kept.append([s, a])
            if e > b:
                kept.append([b, e])
        if kept:
            self._tags[tag] = sorted(kept)
        else:
            self._tags.pop(tag, None)

    def tag_ranges(self, tag: str) -> Tuple[str, ...]:
        out: List[str] = []
        for s, e in sorted(self._tags.get(tag, [])):
            out += [self.idx(s), self.idx(e)]
        return tuple(out)

    def tag_names(self, index=None) -> Tuple[str, ...]:
        if index is None:
            return tuple(sorted(self._tags))
        pos = self.off(index)
        return tuple(sorted(t for t, rs in self._tags.items()
                            for s, e in rs if s <= pos < e))

    def tag_configure(self, *args, **kwargs) -> None:
        return None

    def tag_raise(self, *args, **kwargs) -> None:
        return None

    def dump(self, start: Index, end: Index, tag: bool = False, text: bool = False,
             **_kw) -> List[Tuple[str, str, str]]:
        """Reproduz o ``dump`` do Tk: eventos de tag e texto, em ordem."""
        a = self.off(start)
        b = min(self.off(end), len(self._text))
        if b <= a:
            return []
        events = []
        if tag:
            for t, ranges in self._tags.items():
                for s, e in ranges:
                    if e <= a or s >= b:
                        continue
                    events.append((max(s, a), 0, "tagon", t))
                    if a < e < b:
                        events.append((e, 2, "tagoff", t))
        if text:
            for i in range(a, b):
                events.append((i, 1, "text", self._text[i]))
        events.sort()

        out: List[Tuple[str, str, str]] = []
        buf, buf_at = "", a
        for pos, _order, kind, value in events:
            if kind == "text":
                if not buf:
                    buf_at = pos
                buf += value
                continue
            if buf:
                out.append(("text", buf, self.idx(buf_at)))
                buf = ""
            out.append((kind, value, self.idx(pos)))
        if buf:
            out.append(("text", buf, self.idx(buf_at)))
        return out

    # --------------------------------------------------------------- busca
    def search(self, pattern: str, index: Index = "1.0", stopindex=None,
               nocase: bool = False, backwards: bool = False, wrap: bool = False,
               regexp: bool = False, **_kw) -> str:
        hay = self._text.lower() if nocase else self._text
        needle = pattern.lower() if nocase else pattern
        if not needle:
            return ""
        start = self.off(index)
        stop = self.off(stopindex) if stopindex else len(self._text)
        if backwards:
            pos = hay.rfind(needle, 0, start)
            if pos < 0 and wrap:
                pos = hay.rfind(needle, 0, stop)
        else:
            pos = hay.find(needle, start, stop)
            if pos < 0 and wrap:
                pos = hay.find(needle, 0, stop)
        return self.idx(pos) if pos >= 0 else ""

    # --------------------------------------------- undo do Tk (compatibilidade)
    def edit_modified(self, value=None):
        if value is None:
            return self._modified
        self._modified = bool(value)

    def edit_reset(self) -> None:
        return None

    def edit_undo(self) -> None:
        raise RuntimeError("sem histórico")

    def edit_redo(self) -> None:
        raise RuntimeError("sem histórico")

    def cget(self, key):
        return self._undo if key == "undo" else None

    def configure(self, **kw) -> None:
        if "undo" in kw:
            self._undo = bool(kw["undo"])
