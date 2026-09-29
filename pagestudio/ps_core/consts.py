# -*- coding: utf-8 -*-
"""Constantes globais do RD5 PageStudio (identidade, cores, fontes e gabarito)."""

__all__ = [
    "APP", "VERSION", "FACE", "FACE_HI", "NAVY", "YELLOW", "FONT", "FONT_S",
    "NEW_PAGE", "new_page", "HTML_EXTS", "OPEN_FILETYPES", "SAVE_FILETYPES",
    "IMAGE_FILETYPES", "STYLES", "LINE_TAGS", "BULLET", "HR_TEXT", "VOID",
    "SPECIAL_CHARS",
]

APP = "RD5 PageStudio"
VERSION = "2.0.0"

# Paleta clássica do Office 2000/XP
FACE = "#D4D0C8"      # cinza das barras e painéis
FACE_HI = "#E8E6E0"   # cinza claro (botão ativo)
NAVY = "#0A246A"      # azul das seleções e títulos de painel
YELLOW = "#FFFFE1"    # amarelo das dicas (tooltips)

FONT = ("Tahoma", 9)
FONT_S = ("Tahoma", 8)

NEW_PAGE = """<!DOCTYPE html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<meta name="GENERATOR" content="{app} {version}">
<title>{title}</title>
</head>
<body>
{body}
</body>
</html>
"""

#: Extensões tratadas como página da Web (abrem no modo Design).
HTML_EXTS = (".htm", ".html", ".xhtml")

#: Extensões aceitas na caixa de diálogo "Abrir".
OPEN_FILETYPES = [
    ("Páginas da Web", "*.htm *.html *.xhtml"),
    ("Código", "*.css *.js *.php *.txt *.xml *.json"),
    ("Todos os arquivos", "*.*"),
]

SAVE_FILETYPES = [
    ("Página da Web", "*.htm *.html"),
    ("Todos os arquivos", "*.*"),
]

IMAGE_FILETYPES = [
    ("Imagens", "*.png *.jpg *.jpeg *.gif *.webp *.svg *.bmp *.ico"),
    ("Todos os arquivos", "*.*"),
]

#: Estilo da caixa "Estilo" da barra de formatação.
STYLES = {
    "Normal": None,
    "Título 1": "h1",
    "Título 2": "h2",
    "Título 3": "h3",
    "Lista com marcadores": "li",
    "Pré-formatado": "pre",
}

#: Tags de linha que são mutuamente exclusivas.
LINE_TAGS = ("h1", "h2", "h3", "pre", "li")

BULLET = "\u2022 "          # marcador de lista no modo Design
HR_TEXT = "\u2500" * 40     # linha horizontal no modo Design

#: Elementos vazios (não têm tag de fechamento).
VOID = {"br", "hr", "img", "meta", "link", "input", "base", "col", "area",
        "source", "track", "wbr", "embed", "param"}

#: Caracteres especiais oferecidos no menu Inserir.
SPECIAL_CHARS = [
    ("espaço fixo (\u00a0)", "\u00a0"),
    ("traço (—)", "\u2014"),
    ("meia-traço (–)", "\u2013"),
    ("aspas curvas (“ ”)", "\u201c\u201d"),
    ("apóstrofo (’)", "\u2019"),
    ("reticências (…)", "\u2026"),
    ("símbolo de euro (€)", "\u20ac"),
    ("copyright (©)", "\u00a9"),
    ("marca registrada (®)", "\u00ae"),
    ("grau (°)", "\u00b0"),
]


def new_page(title="Nova Página"):
    """Gera o gabarito de uma página nova."""
    return NEW_PAGE.format(app=APP, version=VERSION, title=title, body="<p></p>")
