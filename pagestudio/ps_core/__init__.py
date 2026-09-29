# -*- coding: utf-8 -*-
"""
ps_core — núcleo do RD5 PageStudio, 100% independente de interface gráfica.

Todo o trabalho "de verdade" do editor (análise do HTML, conversão Design ⇄ HTML,
preservação de blocos avançados, codificação de caracteres, metadados, busca e
substituição, histórico e configurações) vive aqui, para poder ser testado sem
precisar de display nem de Tkinter.

A camada gráfica (``ps_gui``) é intencionalmente fina: ela apenas liga os widgets
do Tkinter a estas funções.
"""

from .consts import (  # noqa: F401
    APP, VERSION, FACE, FACE_HI, NAVY, YELLOW, FONT, FONT_S,
    NEW_PAGE, new_page, HTML_EXTS, OPEN_FILETYPES, SAVE_FILETYPES,
    IMAGE_FILETYPES, STYLES, LINE_TAGS, BULLET, HR_TEXT, VOID, SPECIAL_CHARS,
)
from .htmlutil import (  # noqa: F401
    ReadDoc,
    merge_body,
    merge_head,
    read_document,
    write_text,
    get_title,
    set_title,
    set_meta,
    get_meta,
    set_body_attrs,
    set_charset,
    table_html,
    normalize_newlines,
    body_of,
    validate_html,
    count_words,
    file_stat_signature,
    declared_charset,
)
from .design import (  # noqa: F401
    PROTECTED,
    PROTECTED_PREFIX,
    PROTECTED_LABELS,
    NBSP_CH,
    DesignParser,
    ProtectedBlocks,
    extract_protected,
    parse_to_design,
    inline_html,
    design_to_html,
    is_inline,
)
from .history import DesignHistory, DESIGN_TAGS  # noqa: F401
from .search import (  # noqa: F401
    Match,
    MatchFinder,
    offset_to_index,
    buffer_end,
    replace_span,
    replace_all,
)
from .config import (  # noqa: F401
    Settings,
    autosave_path,
    find_autosaves,
    clear_autosaves,
    base_dir,
    config_path,
    autosave_dir,
)

__all__ = [
    # consts
    "APP", "VERSION", "FACE", "FACE_HI", "NAVY", "YELLOW", "FONT", "FONT_S",
    "NEW_PAGE", "new_page", "HTML_EXTS", "OPEN_FILETYPES", "SAVE_FILETYPES",
    "IMAGE_FILETYPES", "STYLES", "LINE_TAGS", "BULLET", "HR_TEXT", "VOID",
    "SPECIAL_CHARS",
    # htmlutil
    "ReadDoc", "merge_body", "merge_head", "read_document", "write_text",
    "get_title", "set_title", "set_meta", "get_meta", "set_body_attrs",
    "set_charset", "table_html", "normalize_newlines", "body_of",
    "validate_html", "count_words", "file_stat_signature", "declared_charset",
    # design
    "PROTECTED", "PROTECTED_PREFIX", "PROTECTED_LABELS", "NBSP_CH",
    "DesignParser", "ProtectedBlocks", "extract_protected", "parse_to_design",
    "inline_html", "design_to_html", "is_inline",
    # history
    "DesignHistory", "DESIGN_TAGS",
    # search
    "Match", "MatchFinder", "offset_to_index", "buffer_end", "replace_span",
    "replace_all",
    # config
    "Settings", "autosave_path", "find_autosaves", "clear_autosaves",
    "base_dir", "config_path", "autosave_dir",
]
