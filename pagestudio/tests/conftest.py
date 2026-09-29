# -*- coding: utf-8 -*-
"""Configuração da suíte de testes do RD5 PageStudio.

Os testes exercitam o núcleo (``ps_core``), que não depende de Tkinter nem de
display. O teste de fumaça da interface é ignorado automaticamente quando o
ambiente não tem Tkinter disponível.
"""

import sys
from pathlib import Path

import pytest

PAGESTUDIO = Path(__file__).resolve().parent.parent
if str(PAGESTUDIO) not in sys.path:
    sys.path.insert(0, str(PAGESTUDIO))
if str(Path(__file__).resolve().parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent))


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Isola as configurações e os autosaves em uma pasta temporária."""
    data = tmp_path / "rd5data"
    data.mkdir()
    monkeypatch.setenv("RD5_PAGESTUDIO_DIR", str(data))
    return data


@pytest.fixture
def plain_doc():
    from plaindoc import PlainDoc
    return PlainDoc


def load_design(html: str):
    """Constrói o documento de Design a partir de um HTML (como o app faz)."""
    from ps_core import DesignParser, extract_protected
    from plaindoc import PlainDoc

    stripped, blocks = extract_protected(html)
    parser = DesignParser()
    parser.feed(stripped)
    parser.close()
    doc = PlainDoc()
    doc.insert_pieces(parser.out)
    return doc, blocks


def design_html(html: str) -> str:
    """HTML → Design → HTML (o ciclo completo do modo Design)."""
    from ps_core import design_to_html

    doc, blocks = load_design(html)
    return design_to_html(doc, blocks)
