# -*- coding: utf-8 -*-
"""
Utilitários de HTML e de arquivos do RD5 PageStudio.

Cuida de três coisas que o editor antigo fazia de forma frágil:

1. **Codificação** — lê detectando o ``charset`` declarado no próprio arquivo e
   grava preservando a codificação original (com promoção automática para UTF-8
   quando o texto não cabe nela).
2. **Mesclagem** — substitui apenas o conteúdo de ``<body>`` (ou de ``<head>``),
   preservando o resto do documento; se não houver ``<body>``, cria a estrutura.
3. **Metadados** — título, ``description``, ``keywords`` e atributos do ``<body>``,
   inserindo as tags quando elas ainda não existem.
"""

from __future__ import annotations

import html as htmllib
import os
import re
from dataclasses import dataclass
from typing import List, Optional, Tuple

from .consts import VOID, new_page

# Charset declarado no arquivo (meta charset="..." ou http-equiv="Content-Type").
CHARSET_RE = re.compile(rb"charset\s*=\s*[\"']?\s*([a-zA-Z0-9_\-]+)", re.I)

#: Ordem de tentativa quando o arquivo não declara charset.
FALLBACK_ENCODINGS = ("utf-8", "cp1252", "latin-1")

#: Aliases comuns que precisam de tradução antes do codec.lookup do Python.
ENCODING_ALIASES = {
    "ansi_x3.4-1968": "ascii",
    "us-ascii": "ascii",
    "iso-8859-1": "latin-1",
    "latin1": "latin-1",
    "windows-1252": "cp1252",
    "cp-1252": "cp1252",
    "utf8": "utf-8",
}


def normalize_newlines(text: str) -> str:
    """Converte CRLF/CR para LF (é o formato gravado em disco pelo editor)."""
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _lookup(encoding: str) -> Optional[str]:
    """Normaliza um nome de charset; devolve ``None`` se for desconhecido."""
    import codecs

    if not encoding:
        return None
    name = encoding.strip().lower()
    name = ENCODING_ALIASES.get(name, name)
    try:
        codecs.lookup(name)
    except LookupError:
        return None
    return name


def declared_charset(raw: bytes) -> Optional[str]:
    """Lê o charset declarado nos primeiros bytes do arquivo (se houver)."""
    head = raw[:4096]
    m = CHARSET_RE.search(head)
    if not m:
        return None
    return _lookup(m.group(1).decode("ascii", "ignore"))


@dataclass
class ReadDoc:
    """Resultado de :func:`read_document`."""

    path: str
    text: str
    encoding: str
    bom: bool = False


def read_document(path: str) -> ReadDoc:
    """Abre um arquivo de texto respeitando BOM e o charset declarado.

    Levanta ``OSError`` quando o arquivo não pode ser lido (o chamador mostra a
    mensagem de erro) — nunca devolve texto corrompido silenciosamente.
    """
    with open(path, "rb") as fh:
        raw = fh.read()

    bom = raw.startswith(b"\xef\xbb\xbf")
    if bom:
        raw = raw[3:]

    preferred = declared_charset(raw)
    order: List[str] = []
    if preferred:
        order.append(preferred)
    for enc in FALLBACK_ENCODINGS:
        if enc not in order:
            order.append(enc)

    last_error: Optional[Exception] = None
    for enc in order:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, LookupError) as ex:  # pragma: no cover - defensivo
            last_error = ex
            continue
        return ReadDoc(path=path, text=normalize_newlines(text), encoding=enc, bom=bom)

    # Nada funcionou: decodifica como UTF-8 substituindo o que for inválido,
    # mas avisa o chamador usando latin-1 (nunca falha) como última saída.
    if last_error is not None:
        text = raw.decode("latin-1")
        return ReadDoc(path=path, text=normalize_newlines(text), encoding="latin-1", bom=bom)
    raise OSError(f"Não foi possível decodificar: {path}")  # pragma: no cover


def set_charset(code: str, encoding: str) -> str:
    """Ajusta a declaração de charset do documento para ``encoding``."""
    if not re.search(r"charset\s*=", code, re.I):
        return set_meta(code, "charset", encoding, http_equiv=False)
    return re.sub(r"(charset\s*=\s*[\"']?)[^\"'\s>]+", lambda m: m.group(1) + encoding,
                  code, count=1, flags=re.I)


def write_text(path: str, text: str, encoding: str = "utf-8", bom: bool = False) -> Tuple[str, bool]:
    """Grava ``text`` em ``path``.

    Devolve ``(codificação_usada, promovido_para_utf8)``. Se algum caractere não
    puder ser representado na codificação original, o texto é promovido para
    UTF-8 (e o ``charset`` do documento é corrigido) para nunca perder conteúdo.
    """
    promoted = False
    enc = _lookup(encoding) or "utf-8"
    try:
        data = text.encode(enc)
    except (UnicodeEncodeError, LookupError):
        text = set_charset(text, "utf-8")
        data = text.encode("utf-8")
        enc, promoted = "utf-8", True

    if bom and not data.startswith(b"\xef\xbb\xbf"):
        data = b"\xef\xbb\xbf" + data

    with open(path, "wb") as fh:
        fh.write(data)
    return enc, promoted


# ------------------------------------------------------------------ mesclagem
_BODY_RE = re.compile(r"(<body[^>]*>)(.*)(</body\s*>)", re.S | re.I)
_HEAD_RE = re.compile(r"(<head[^>]*>)(.*)(</head\s*>)", re.S | re.I)
_HTML_RE = re.compile(r"</html\s*>", re.I)


def merge_body(code: str, body_html: str, title: Optional[str] = None) -> str:
    """Substitui somente o conteúdo de ``<body>`` preservando ``<head>`` e afins.

    Quando o documento não tem ``<body>``, cria a estrutura mínima em vez de
    descartar o que havia antes (comportamento do 1.0.0, que perdia o arquivo).
    """
    m = _BODY_RE.search(code)
    if m:
        return code[:m.end(1)] + "\n" + body_html + "\n" + code[m.start(3):]

    page = new_page(title or get_title(code) or "Nova Página")
    leftover = code
    hm = re.search(r"<head[^>]*>(.*)</head\s*>", code, re.S | re.I)
    if hm:
        # Mantém o <head> original e guarda o que estava fora dele.
        page = re.sub(r"(<head[^>]*>)(.*)(</head\s*>)",
                      lambda mm: mm.group(1) + hm.group(1) + mm.group(3),
                      page, count=1, flags=re.S | re.I)
        leftover = (code[:hm.start()] + code[hm.end():]).strip()
    else:
        leftover = re.sub(r"<!doctype[^>]*>|</?html[^>]*>", " ", code,
                          flags=re.S | re.I).strip()
    body = (leftover + "\n" if leftover else "") + body_html
    return re.sub(r"(<body[^>]*>)(.*)(</body\s*>)",
                  lambda mm: mm.group(1) + "\n" + body + "\n" + mm.group(3),
                  page, count=1, flags=re.S | re.I)


def merge_head(code: str, head_html: str) -> str:
    """Substitui somente o conteúdo de ``<head>``."""
    m = _HEAD_RE.search(code)
    if m:
        return code[:m.end(1)] + "\n" + head_html + "\n" + code[m.start(3):]
    return code  # sem <head> não há o que mesclar


# ----------------------------------------------------------------- metadados
def _esc(value: str, quote: bool = False) -> str:
    return htmllib.escape(value or "", quote=quote)


def get_title(code: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title\s*>", code, re.S | re.I)
    return htmllib.unescape(m.group(1).strip()) if m else ""


def set_title(code: str, title: str) -> str:
    """Define o ``<title>``, criando a tag dentro do ``<head>`` se preciso."""
    value = _esc(title, quote=False)
    m = re.search(r"(<title[^>]*>)(.*?)(</title\s*>)", code, re.S | re.I)
    if m:
        return code[:m.start(2)] + value + code[m.end(2):]
    if re.search(r"</head\s*>", code, re.I):
        return re.sub(r"(</head\s*>)", f"<title>{value}</title>\n\\1", code, count=1, flags=re.I)
    if re.search(r"<head[^>]*>", code, re.I):
        return re.sub(r"(<head[^>]*>)", f"\\1\n<title>{value}</title>", code, count=1, flags=re.I)
    return code


def get_meta(code: str, name: str) -> str:
    """Lê ``<meta name="...">`` ou ``<meta http-equiv="...">``."""
    pat = re.compile(
        r"<meta[^>]+(?:name|http-equiv|property)\s*=\s*[\"']%s[\"'][^>]*>" % re.escape(name),
        re.I)
    m = pat.search(code)
    if not m:
        return ""
    c = re.search(r"content\s*=\s*[\"']([^\"']*)[\"']", m.group(0), re.I)
    return htmllib.unescape(c.group(1)) if c else ""


def set_meta(code: str, name: str, value: str, http_equiv: bool = False) -> str:
    """Cria ou atualiza uma tag ``<meta>``, sempre dentro do ``<head>``."""
    attr = "http-equiv" if http_equiv else "name"
    key = "charset" if name.lower() == "charset" else name
    if name.lower() == "charset":
        attr = "charset"
    pat = re.compile(
        r"<meta[^>]+(?:name|http-equiv|property|charset)\s*=\s*[\"']?%s[\"']?[^>]*>" % re.escape(key),
        re.I)
    if name.lower() == "charset":
        tag = f'<meta charset="{_esc(value)}">'
    else:
        tag = f'<meta {attr}="{_esc(name)}" content="{_esc(value, quote=True)}">'

    m = pat.search(code)
    if m:
        return code[:m.start()] + tag + code[m.end():]

    if re.search(r"</head\s*>", code, re.I):
        return re.sub(r"(</head\s*>)", tag + "\n\\1", code, count=1, flags=re.I)
    if re.search(r"<head[^>]*>", code, re.I):
        return re.sub(r"(<head[^>]*>)", "\\1\n" + tag, code, count=1, flags=re.I)
    return tag + "\n" + code


def set_body_attrs(code: str, bgcolor: str = "", text: str = "", link: str = "") -> str:
    """Define atributos clássicos do ``<body>`` (como o FrontPage fazia)."""
    m = re.search(r"<body([^>]*)>", code, re.I)
    if not m:
        return code
    attrs = m.group(1)
    for key, val in (("bgcolor", bgcolor), ("text", text), ("link", link)):
        attrs = re.sub(r"\s%s\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s>]+)" % key, "", attrs, flags=re.I)
        if val:
            attrs += f' {key}="{_esc(val)}"'
    return code[:m.start()] + f"<body{attrs}>" + code[m.end():]


# ------------------------------------------------------------------- tabelas
def table_html(rows: int, cols: int, border: int = 1, width: str = "100%",
               padding: int = 4, header: bool = True,
               align: str = "", color: str = "") -> str:
    """Gera o HTML de uma tabela simples no estilo Office 2000."""
    rows = max(1, int(rows))
    cols = max(1, int(cols))
    style_bits = ["border-collapse: collapse", f"width: {width or '100%'}"]
    attrs = [f'border="{max(0, int(border))}"', f'cellpadding="{max(0, int(padding))}"',
             'cellspacing="0"', 'style="' + "; ".join(style_bits) + '"']

    lines = [f"<table {' '.join(attrs)}>"]
    for r in range(rows):
        lines.append("  <tr>")
        is_head = header and r == 0
        for _c in range(cols):
            cell = "th" if is_head else "td"
            extra = ' style="text-align: left; background: #E8E6E0"' if is_head else ""
            lines.append(f"    <{cell}{extra}>&nbsp;</{cell}>")
        lines.append("  </tr>")
    lines.append("</table>")
    html = "\n".join(lines)

    # Aplica formatação "herdada" da seleção (cor e alinhamento) por fora.
    if color:
        html = f'<font color="{_esc(color)}">{html}</font>'
    if align and align != "left":
        html = f'<div style="text-align: {align}">{html}</div>'
    return html


def body_of(code: str) -> str:
    """Conteúdo entre ``<body>`` e ``</body>`` (ou o documento todo)."""
    m = _BODY_RE.search(code)
    if m:
        return code[m.end(1):m.start(3)]
    m = re.search(r"<body[^>]*>(.*)", code, re.S | re.I)
    return m.group(1) if m else code


def validate_html(code: str) -> List[str]:
    """Checagem rápida de problemas comuns (sem sair do editor).

    Não é um validador W3C: o objetivo é pegar o que o FrontPage pegava —
    falta de DOCTYPE/charset/título, tags abertas demais ou fechadas a menos e
    atributos sem aspas.
    """
    issues: List[str] = []
    if not re.search(r"<!doctype\s+html", code, re.I):
        issues.append("O documento não declara <!DOCTYPE html>.")
    if not re.search(r"charset\s*=", code, re.I):
        issues.append("Nenhuma declaração de charset (use <meta charset=\"utf-8\">).")
    if not get_title(code):
        issues.append("A página não tem <title>.")

    body = body_of(code)
    # Ignora comentários e o conteúdo de <script>/<style> na checagem de tags.
    clean = re.sub(r"<!--.*?-->", " ", body, flags=re.S)
    clean = re.sub(r"(<script\b.*?</script\s*>|<style\b.*?</style\s*>)", " ",
                   clean, flags=re.S | re.I)

    local_void = set(VOID)
    stack: List[Tuple[str, int]] = []
    for m in re.finditer(r"<(/?)([A-Za-z][A-Za-z0-9:_-]*)([^>]*?)(/?)>", clean, re.S):
        closing, name, attrs, self_close = m.group(1), m.group(2).lower(), m.group(3), m.group(4)
        line = clean.count("\n", 0, m.start()) + 1
        if closing:
            if not stack:
                issues.append(f"Linha {line}: </{name}> sem tag de abertura.")
                continue
            if stack[-1][0] == name:
                stack.pop()
            else:
                names = [t for t, _ in stack]
                if name in names:
                    while stack and stack[-1][0] != name:
                        issues.append(f"Linha {line}: <{stack[-1][0]}> não foi fechada antes de </{name}>.")
                        stack.pop()
                    if stack:
                        stack.pop()
                else:
                    issues.append(f"Linha {line}: </{name}> não tem abertura correspondente.")
        elif name not in local_void and not self_close:
            stack.append((name, line))
        if re.search(r"=\s*[^\s\"'>]", attrs):
            issues.append(f"Linha {line}: atributo de <{name}> sem aspas.")

    for name, line in stack:
        issues.append(f"Linha {line}: <{name}> ficou sem fechamento.")
    return issues


def count_words(text: str) -> int:
    """Quantidade de palavras de um texto (para o contador do modo Design)."""
    return len([w for w in re.split(r"\s+", text) if w.strip(" \u2423")])


def file_stat_signature(path: Optional[str]) -> Optional[Tuple[float, int]]:
    """Assinatura (mtime, tamanho) usada para detectar edição externa."""
    if not path or not os.path.isfile(path):
        return None
    try:
        st = os.stat(path)
    except OSError:
        return None
    return (st.st_mtime, st.st_size)
