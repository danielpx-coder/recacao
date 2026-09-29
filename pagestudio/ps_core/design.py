# -*- coding: utf-8 -*-
"""
Conversão Design ⇄ HTML do RD5 PageStudio.

O modo Design é uma visão *simplificada* e baseada em linhas (cada parágrafo,
título ou item de lista vira uma linha do widget de texto). A versão 1.0.0
destruía tudo o que não cabia nesse modelo — tabelas, formulários, scripts,
estilos — assim que o usuário digitava uma vírgula em Design.

A versão 2.0 resolve isso com **blocos protegidos**: antes de analisar o HTML,
os elementos avançados são retirados do documento e guardados intactos numa
lista; no lugar deles entra um marcador curto (``@@RD5PB0@@``), que o modo
Design mostra como uma linha cinza "[Tabela 1 — conteúdo protegido]". Ao gravar,
o marcador devolve o HTML original, byte por byte.

Todas as funções daqui trabalham sobre "documentos de texto" genéricos: tanto o
widget ``tkinter.Text`` quanto uma ``str`` comum implementam ``get``, ``dump``
e ``tag_names``, o que permite testar a conversão sem interface gráfica.
"""

from __future__ import annotations

import html as htmllib
import os
import re
from html.parser import HTMLParser
from typing import Iterable, List, Optional, Sequence, Set, Tuple

from .consts import BULLET, HR_TEXT, LINE_TAGS, VOID

#: Elementos que o modo Design não representa e que precisam ser preservados.
PROTECTED = ("table", "form", "script", "style", "iframe", "svg", "canvas",
             "video", "audio", "select", "textarea", "object", "map", "noscript",
             "details", "dialog", "template", "math")

#: Rótulo amigável de cada bloco protegido.
PROTECTED_LABELS = {
    "table": "Tabela",
    "form": "Formulário",
    "script": "Script",
    "style": "Folha de estilos",
    "iframe": "Quadro embutido (iframe)",
    "svg": "Gráfico vetorial (SVG)",
    "canvas": "Canvas",
    "video": "Vídeo",
    "audio": "Áudio",
    "select": "Lista suspensa",
    "textarea": "Área de texto",
    "object": "Objeto embutido",
    "map": "Mapa de imagem",
    "noscript": "Conteúdo noscript",
    "details": "Bloco recolhível",
    "dialog": "Caixa de diálogo",
    "template": "Modelo (template)",
    "math": "Fórmula (MathML)",
}

PROTECTED_PREFIX = "@@RD5PB"
_PROTECTED_RE = re.compile(r"@@RD5PB(\d+)@@")

#: Somente o próprio elemento conta profundidade: HTML real raramente é
#: perfeitamente balanceado (``<div>`` sem fechamento é comum) e contar tags
#: estruturais faria o bloco protegido "engolir" o resto do documento.

_TAG_RE = re.compile(r"<(/?)([A-Za-z][A-Za-z0-9:_-]*)([^>]*?)(/?)>", re.S)

#: Formatação inline reconhecida pelo modo Design.
INLINE_TAGS = ("bold", "italic", "underline")

#: Caractere privado usado para representar espaços "duros" no modo Design.
#: O widget de texto do Tk reduz sequências de espaços a um só na hora de
#: mostrar; usando este caractere o texto continua idêntico ao HTML e a
#: conversão de volta gera ``&nbsp;``.
NBSP_CH = "\u2423"


class ProtectedBlocks:
    """Guarda o HTML original dos elementos avançados da página."""

    def __init__(self, items: Optional[Sequence[Tuple[str, str]]] = None):
        self.items: List[Tuple[str, str]] = list(items or [])

    def __len__(self) -> int:
        return len(self.items)

    def __bool__(self) -> bool:
        return bool(self.items)

    @property
    def tags(self) -> Set[str]:
        """Nomes de tags de design correspondentes (``pb:0``, ``pb:1``...)."""
        return {f"pb:{i}" for i in range(len(self.items))}

    def get(self, index: int) -> str:
        if 0 <= index < len(self.items):
            return self.items[index][1]
        return ""

    def label(self, index: int) -> str:
        if not (0 <= index < len(self.items)):
            return "Conteúdo protegido"
        tag = self.items[index][0]
        return f"{PROTECTED_LABELS.get(tag, tag.capitalize())} {index + 1}"


def extract_protected(html: str, protected: Iterable[str] = PROTECTED) -> Tuple[str, ProtectedBlocks]:
    """Remove os elementos avançados do ``html`` e devolve marcadores + conteúdo.

    Elementos aninhados são capturados junto com o pai (uma tabela dentro de um
    formulário vira um único bloco), evitando marcadores quebrados.
    """
    names = set(protected)
    items: List[Tuple[str, str]] = []
    out: List[str] = []
    pos, n, last = 0, len(html), 0

    def close_tag(tag: str, start: int) -> int:
        """Índice logo após o fechamento de ``tag`` (com aninhamento contado)."""
        depth, i = 1, start
        while i < n:
            m = _TAG_RE.match(html, i)
            if not m:
                nxt = html.find("<", i + 1)
                i = n if nxt < 0 else nxt
                continue
            if m.group(2).lower() == tag:
                depth += -1 if m.group(1) else (0 if m.group(4) else 1)
                if depth <= 0:
                    return m.end()
            i = m.end()
        return n

    while True:
        lt = html.find("<", pos)
        if lt < 0:
            break
        if html.startswith("<!--", lt):
            end = html.find("-->", lt + 4)
            pos = n if end < 0 else end + 3
            continue
        if html.startswith("<!", lt) or html.startswith("<?", lt):
            end = html.find(">", lt)
            pos = n if end < 0 else end + 1
            continue
        m = _TAG_RE.match(html, lt)
        if not m:
            pos = lt + 1
            continue
        closing, name = m.group(1), m.group(2).lower()
        if closing or name not in names:
            pos = m.end()
            continue

        end = close_tag(name, m.end())
        block = html[lt:end]
        idx = len(items)
        items.append((name, block))
        out.append(html[last:lt])
        if out and not out[-1].endswith("\n"):
            out.append("\n")
        out.append(f"{PROTECTED_PREFIX}{idx}@@\n")
        last = pos = end

    out.append(html[last:])
    return "".join(out), ProtectedBlocks(items)


# ----------------------------------------------------------------- analisador
class DesignParser(HTMLParser):
    """Transforma HTML em pedaços ``(texto, tags)`` para o widget de Design."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out: List[Tuple[str, Tuple[str, ...]]] = []
        self.title = ""
        self.stack: List[Tuple[str, List[str]]] = []
        self.in_title = False
        self.in_head = False
        self.in_pre = False
        self.skip = 0
        self.lossy = False

    # -- auxiliares ---------------------------------------------------------
    def _tags(self) -> Tuple[str, ...]:
        return tuple(t for _name, ts in self.stack for t in ts)

    def _nl(self) -> None:
        if self.out and not self.out[-1][0].endswith("\n"):
            self.out.append(("\n", self._tags()))

    @staticmethod
    def _align(attrs) -> List[str]:
        d = dict(attrs)
        style = (d.get("style") or "").lower()
        al = (d.get("align") or "").lower()
        m = re.search(r"text-align\s*:\s*(\w+)", style)
        if m:
            al = m.group(1)
        return [al] if al in ("center", "right") else []

    @staticmethod
    def _font_tags(attrs) -> List[str]:
        """Extrai cor e tamanho de ``<font>``/``<span style=...>``."""
        d = dict(attrs)
        tags: List[str] = []
        color = d.get("color")
        if not color:
            m = re.search(r"(?<![-\w])color\s*:\s*([^;\"']+)", d.get("style") or "")
            color = m.group(1).strip() if m else None
        if color:
            tags.append(f"c:{color}")
        size = d.get("size")
        if not size:
            m = re.search(r"font-size\s*:\s*(\d+)", d.get("style") or "")
            size = m.group(1) if m else None
        if size and str(size).isdigit() and 1 <= int(size) <= 7:
            tags.append(f"s:{size}")
        return tags

    # -- eventos ------------------------------------------------------------
    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == "head":
            self.in_head = True
        if not self.in_head and tag in ("script", "style", "table", "form"):
            self.lossy = True
        if tag == "title":
            self.in_title = True
        if tag in ("script", "style"):
            self.skip += 1

        tags: List[str] = []
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self._nl()
            tags = ["h1" if tag == "h1" else "h2" if tag == "h2" else "h3"] + self._align(attrs)
        elif tag in ("p", "div", "blockquote"):
            self._nl()
            tags = self._align(attrs)
        elif tag == "center":
            self._nl()
            tags = ["center"]
        elif tag == "pre":
            self._nl()
            self.in_pre = True
            tags = ["pre"]
        elif tag in ("ul", "ol", "tr"):
            self._nl()
        elif tag == "li":
            self._nl()
            tags = ["li"]
            self.stack.append((tag, tags))
            self.out.append((BULLET, self._tags()))
            return
        elif tag in ("b", "strong"):
            tags = ["bold"]
        elif tag in ("i", "em"):
            tags = ["italic"]
        elif tag == "u":
            tags = ["underline"]
        elif tag == "a" and d.get("href"):
            tags = [f"a:{d['href']}"]
        elif tag in ("font", "span"):
            tags = self._font_tags(attrs)
        elif tag in ("td", "th"):
            if self.out and not self.out[-1][0].endswith("\n"):
                self.out.append(("\t", self._tags()))
        elif tag == "br":
            self.out.append(("\n", self._tags()))
        elif tag == "hr":
            self._nl()
            self.out.append((HR_TEXT + "\n", ("hr",)))
        elif tag == "img":
            src = d.get("src") or ""
            if src:
                name = os.path.basename(src) or src
                self.out.append((f"[Imagem: {name}]", (f"img:{src}",)))

        if tag not in VOID:
            self.stack.append((tag, tags))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False
        if tag == "title":
            self.in_title = False
        if tag in ("script", "style") and self.skip:
            self.skip -= 1
        if tag == "pre":
            self.in_pre = False
        for i in range(len(self.stack) - 1, -1, -1):
            if self.stack[i][0] == tag:
                del self.stack[i]
                break
        if tag in ("p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "tr",
                   "ul", "ol", "pre", "table", "center", "blockquote"):
            self._nl()

    def handle_data(self, data):
        if self.in_title:
            self.title += data
            return
        if self.skip or self.in_head:
            return
        if not self.in_pre:
            data = data.replace("\xa0", NBSP_CH)
            data = re.sub(r"[\n\r\t]+", " ", data)
            # Duas ou mais espaços viram espaços "duros" (o HTML os esmagaria).
            data = re.sub(r" {2,}", lambda m: NBSP_CH * (len(m.group()) - 1) + " ", data)
            data = re.sub(r"[ \n\r\t\f\v]+", " ", data)
            if not self.out or self.out[-1][0].endswith("\n"):
                data = data.lstrip(" \n\r\t\f\v")
            if data.endswith("\n"):
                # Espaço no fim da linha não significa nada em HTML.
                data = re.sub(r"[ \u2423]+(\n+)$", r"\1", data)
        if data:
            self.out.append((data, self._tags()))


def parse_to_design(code: str) -> DesignParser:
    """Atalho: analisa ``code`` e devolve o analisador já alimentado."""
    p = DesignParser()
    p.feed(code)
    p.close()
    return p


# --------------------------------------------------------------- design → html
def is_inline(tag: str) -> bool:
    """Diz se a tag de design é formatação inline (preservada no HTML)."""
    return tag in INLINE_TAGS or tag.startswith(("a:", "c:", "img:", "s:"))


def _segments(dump_items: Iterable[Tuple[str, str, Optional[str]]],
              active: Set[str], skip: int = 0) -> List[Tuple[frozenset, str]]:
    """Agrupa o resultado de ``dump`` em trechos com o mesmo conjunto de tags."""
    segs: List[Tuple[frozenset, str]] = []
    for key, value, _idx in dump_items:
        if key == "tagon" and is_inline(value):
            active.add(value)
        elif key == "tagoff":
            active.discard(value)
        elif key == "text":
            if not value:
                continue
            if not value.strip():
                # Preserva espaços em branco isolados entre trechos formatados.
                value = value.replace("\n", "")
                if not value:
                    continue
            fs = frozenset(active)
            if segs and segs[-1][0] == fs:
                segs[-1][1] += value
            else:
                segs.append([fs, value])  # type: ignore[arg-type]

    if skip:
        remaining = skip
        for seg in segs:
            cut = min(remaining, len(seg[1]))
            seg[1] = seg[1][cut:]
            remaining -= cut
            if not remaining:
                break
        segs = [seg for seg in segs if seg[1]]
    return [(fs, txt) for fs, txt in segs]


def _escape_text(text: str, nbsp: bool = True) -> str:
    """Escapa o texto e converte espaços em ``&nbsp;`` (como fazia o FrontPage).

    Usar ``&nbsp;`` garante duas coisas: o navegador não "encolhe" sequências de
    espaços e a conversão HTML → Design → HTML é estável (o ``&nbsp;`` volta a
    ser ``&nbsp;``). Dentro de ``<pre>`` (``nbsp=False``) os espaços ficam
    literais, porque lá o navegador já os preserva.
    """
    text = _PROTECTED_RE.sub("", text.replace("\n", ""))
    out = htmllib.escape(text, quote=False)
    if nbsp:
        out = out.replace(NBSP_CH, "&nbsp;").replace(" ", "&nbsp;")
    else:
        out = out.replace(NBSP_CH, " ")
    return out


_TRAILING_WS_RE = re.compile(r"[ \u2423]+$")


def _wrap(fs: frozenset, text: str, keep_spaces: bool = False) -> str:
    """Aplica a formatação inline de ``fs`` ao ``text`` escapado.

    O espaço que fecha um trecho formatado fica *fora* das tags (``<b>x</b> y``
    em vez de ``<b>x y</b>``): renderiza igual e evita que a formatação "ande"
    a cada ciclo Design ⇄ HTML. Em ``<pre>`` (``keep_spaces``) nada é movido.
    """
    for tag in fs:
        if tag.startswith("img:"):
            return f'<img src="{htmllib.escape(tag[4:], quote=True)}" alt="">'
    m = None if keep_spaces else _TRAILING_WS_RE.search(text)
    trail = m.group() if m else ""
    core = text[:m.start()] if m else text
    if not core.strip(" \u2423"):
        return _escape_text(text, nbsp=not keep_spaces)
    out = _escape_text(core, nbsp=not keep_spaces)
    if not out:
        return ""
    if "underline" in fs:
        out = f"<u>{out}</u>"
    if "italic" in fs:
        out = f"<i>{out}</i>"
    if "bold" in fs:
        out = f"<b>{out}</b>"
    for tag in sorted(t for t in fs if t.startswith(("c:", "s:"))):
        if tag.startswith("c:"):
            out = f'<font color="{htmllib.escape(tag[2:], quote=True)}">{out}</font>'
        else:
            out = f'<font size="{tag[2:]}">{out}</font>'
    for tag in fs:
        if tag.startswith("a:"):
            out = f'<a href="{htmllib.escape(tag[2:], quote=True)}">{out}</a>'
    return out + _escape_text(trail, nbsp=not keep_spaces)


def inline_html(doc, line: int, skip: int = 0, active: Optional[Set[str]] = None,
                keep_spaces: bool = False) -> str:
    """Converte a linha ``line`` do documento de Design em HTML inline."""
    start, end = f"{line}.0", f"{line}.end"
    try:
        items = doc.tag_names(start)
    except Exception:  # pragma: no cover - defensivo (índice inválido)
        return ""
    act = {t for t in (active or set()) if is_inline(t)}
    act |= {t for t in items if is_inline(t)}
    html = "".join(_wrap(fs, txt, keep_spaces)
                   for fs, txt in _segments(doc.dump(start, end, tag=True, text=True), act, skip))
    # Marcadores de bloco protegido nunca viram texto visível no HTML.
    return _PROTECTED_RE.sub("", html)


def _design_tags(doc, blocks: Optional[ProtectedBlocks], known: Optional[Set[str]]) -> Set[str]:
    tags = set(known or ())
    try:
        tags |= set(doc.tag_names())
    except Exception:  # pragma: no cover - defensivo
        pass
    if blocks:
        tags |= blocks.tags
    return tags


def design_to_html(doc, blocks: Optional[ProtectedBlocks] = None,
                   known_tags: Optional[Set[str]] = None) -> str:
    """Gera o HTML do ``<body>`` a partir do documento de Design."""
    text = doc.get("1.0", "end-1c")
    if not text:
        return ""
    lines = text.split("\n")
    design_tags = _design_tags(doc, blocks, known_tags)
    parts: List[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            parts.append("</ul>")
            in_list = False

    for n, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            tags = set(doc.tag_names(f"{n}.0"))
        except Exception:  # pragma: no cover - defensivo
            tags = set()
        if "pre" not in tags:
            line = line.rstrip(" \u2423\t")
            if not line.strip():
                continue

        if "hr" in tags:
            close_list()
            parts.append("<hr>")
            continue

        # Blocos protegidos: devolve o HTML original sem tocar nele.
        protected = [t for t in tags if t.startswith("pb:") and t in design_tags]
        if protected or _PROTECTED_RE.search(line):
            close_list()
            pieces = _PROTECTED_RE.split(line)
            for i, piece in enumerate(pieces):
                if i % 2:
                    raw = blocks.get(int(piece)) if blocks else ""
                    if raw:
                        parts.append(raw)
            residue = _PROTECTED_RE.sub("", line).strip(" \u2423\t")
            if residue:
                parts.append(f"<p>{inline_html(doc, n)}</p>")
            continue

        kind = next((k for k in LINE_TAGS if k in tags), None)
        if kind == "li":
            if not in_list:
                parts.append("<ul>")
                in_list = True
            skip = len(BULLET) if line.startswith(BULLET) else 0
            parts.append(f"  <li>{inline_html(doc, n, skip=skip)}</li>")
            continue

        close_list()
        inner = inline_html(doc, n, keep_spaces=("pre" in tags))
        align = "center" if "center" in tags else "right" if "right" in tags else None
        style = f' style="text-align: {align}"' if align else ""
        tag_name = kind or "p"
        parts.append(f"<{tag_name}{style}>{inner}</{tag_name}>")

    close_list()
    return "\n".join(parts)
