# -*- coding: utf-8 -*-
"""
Motor de localizar e substituir.

Funciona com qualquer "documento de texto" que responda a ``get`` e ``search``
— o ``tkinter.Text`` do modo Design, o do modo Código ou uma simples ``str`` —
o que torna a lógica testável sem interface gráfica.

Suporta: maiúsculas/minúsculas, palavra inteira, expressão regular, direção
(anterior/próximo) e volta ao início do documento.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

Index = str


@dataclass
class Match:
    """Uma ocorrência encontrada (índices no formato ``linha.coluna``)."""

    start: Index
    end: Index


def buffer_end(doc) -> str:
    """Índice do fim real do texto (o Tk mantém uma quebra de linha fantasma)."""
    return "end-1c" if _is_tk(doc) else "end"


def _is_tk(doc) -> bool:
    return hasattr(doc, "compare")


def offset_to_index(text: str, offset: int) -> Index:
    """Converte deslocamento de caracteres em índice ``linha.coluna``."""
    offset = max(0, min(offset, len(text)))
    head = text[:offset]
    return f"{head.count(chr(10)) + 1}.{offset - (head.rfind(chr(10)) + 1)}"


def replace_span(doc, start: Index, end: Index, replacement: str) -> None:
    """Troca o trecho entre ``start`` e ``end`` por ``replacement``."""
    if _is_tk(doc):
        doc.delete(start, end)
        doc.insert(start, replacement)
    else:  # pragma: no cover - usado apenas por str em testes
        doc.delete(start, end)
        doc.insert(start, replacement)


class MatchFinder:
    """Encontra ocorrências de ``pattern`` em ``doc``."""

    def __init__(self, doc, pattern: str, case: bool = False, regex: bool = False,
                 whole: bool = False):
        self.doc = doc
        self.pattern = pattern or ""
        self.case = bool(case)
        self.regex = bool(regex)
        self.whole = bool(whole)
        self._compiled: Optional[re.Pattern] = None
        self.error: Optional[str] = None

        if not self.pattern:
            return
        try:
            if self.regex:
                flags = 0 if self.case else re.IGNORECASE
                self._compiled = re.compile(self.pattern, flags)
            else:
                escaped = re.escape(self.pattern)
                if self.whole:
                    escaped = r"(?<!\w)" + escaped + r"(?!\w)"
                self._compiled = re.compile(escaped, 0 if self.case else re.IGNORECASE)
        except re.error as ex:
            self.error = str(ex)

    # -- utilidades ---------------------------------------------------------
    @property
    def ok(self) -> bool:
        return self._compiled is not None

    def text(self) -> str:
        return self.doc.get("1.0", buffer_end(self.doc))

    def _span_to_match(self, text: str, span: Tuple[int, int]) -> Match:
        return Match(offset_to_index(text, span[0]), offset_to_index(text, span[1]))

    # -- busca --------------------------------------------------------------
    def find(self, start: Index = "insert", backward: bool = False,
             wrap: bool = True) -> Optional[Match]:
        """Próxima ocorrência a partir de ``start`` (``None`` se não houver)."""
        if not self.ok:
            return None
        doc, text = self.doc, self.text()
        end = buffer_end(doc)

        if not self.regex and not self.whole:
            # Caminho rápido: busca nativa do widget.
            kw = dict(nocase=not self.case, regexp=False)
            if _is_tk(doc):
                kw["stopindex"] = end
            found = doc.search(self.pattern, start, backwards=backward, wrap=wrap, **kw)
            if found:
                return Match(doc.index(found), doc.index(f"{found}+{len(self.pattern)}c"))
            return None

        # Caminho geral (regex / palavra inteira): varre o texto e converte.
        try:
            base = doc.index(start) if _is_tk(doc) else start
        except Exception:  # pragma: no cover - defensivo
            base = "1.0"
        here = self._to_offset(text, base)
        matches = list(self._compiled.finditer(text))
        if not matches:
            return None
        if backward:
            picks = [m for m in matches if m.start() < here]
            if picks:
                return self._span_to_match(text, picks[-1].span())
            return self._span_to_match(text, matches[-1].span()) if wrap else None
        picks = [m for m in matches if m.start() >= here]
        if picks:
            return self._span_to_match(text, picks[0].span())
        return self._span_to_match(text, matches[0].span()) if wrap else None

    def find_all(self) -> List[Match]:
        """Todas as ocorrências do documento (para "substituir tudo" e contador)."""
        text = self.text()
        return [self._span_to_match(text, span) for span in self.spans()]

    def spans(self) -> List[Tuple[int, int]]:
        """Deslocamentos ``(início, fim)`` de todas as ocorrências não vazias."""
        if not self.ok:
            return []
        text = self.text()
        return [m.span() for m in self._compiled.finditer(text) if m.end() > m.start()]

    def count(self) -> int:
        return len(self.spans())

    # -- interno ------------------------------------------------------------
    def _to_offset(self, text: str, index: Index) -> int:
        try:
            line, col = index.split(".")
            line, col = int(line), int(col)
        except (ValueError, AttributeError):
            return 0
        lines = text.split("\n")
        offset = sum(len(l) + 1 for l in lines[:max(0, line - 1)])
        return min(offset + max(0, col), len(text))


def replace_all(doc, pattern: str, replacement: str, case: bool = False,
                regex: bool = False, whole: bool = False) -> int:
    """Substitui todas as ocorrências e devolve quantas trocas foram feitas."""
    finder = MatchFinder(doc, pattern, case=case, regex=regex, whole=whole)
    if not finder.ok:
        return 0
    pendentes = finder.spans()
    total = len(pendentes)
    # Sempre da última ocorrência para a primeira: assim as anteriores não se
    # deslocam. O texto é relido a cada passo porque o tamanho pode mudar.
    while pendentes:
        start_off, end_off = pendentes.pop()
        text = finder.text()
        replace_span(doc, offset_to_index(text, start_off),
                     offset_to_index(text, end_off), replacement)
    return total
