# -*- coding: utf-8 -*-
"""
Teste de fumaça da interface gráfica.

Só roda quando o ambiente tem Tkinter **e** um display disponível (no Windows
do usuário isso sempre acontece; em CI/headless o teste é ignorado com uma
mensagem clara, em vez de falhar de mentirinha).
"""

import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("RD5_SKIP_GUI") == "1",
    reason="interface gráfica desativada por RD5_SKIP_GUI")


def _tk_disponivel():
    try:
        import tkinter  # noqa: F401  (só a presença já basta)
    except Exception as ex:  # pragma: no cover - ambiente sem Tk
        return False, f"Tkinter indisponível: {ex}"
    try:
        root = __import__("tkinter").Tk()
        root.destroy()
    except Exception as ex:  # pragma: no cover - sem display (headless)
        return False, f"sem display: {ex}"
    return True, ""


OK, MOTIVO = _tk_disponivel()
requires_tk = pytest.mark.skipif(not OK, reason=MOTIVO or "Tkinter indisponível")


@requires_tk
def test_aplicativo_abre_e_edita(tmp_path, monkeypatch):
    """Abre o app, edita em Design e confere o HTML gerado."""
    monkeypatch.setenv("RD5_PAGESTUDIO_DIR", str(tmp_path / "cfg"))
    from ps_gui.app import App

    alvo = tmp_path / "pagina.htm"
    alvo.write_text(
        '<!DOCTYPE html><html><head><meta charset="utf-8"><title>T</title></head>'
        '<body><h1>Título</h1><p>Parágrafo</p>'
        '<table><tr><td>célula</td></tr></table></body></html>', encoding="utf-8")

    app = App(str(alvo))
    try:
        app.update_idletasks()
        assert app.mode == "design"
        design = app.text.get("1.0", "end-1c")
        assert "Título" in design
        assert "Parágrafo" in design
        assert "célula" not in design           # tabela vira bloco protegido
        assert "@@RD5PB0@@" in design

        # edição no modo Design + sincronização para o código
        app.text.insert("end", "\nNovo parágrafo")
        app._touch_design()
        html = app.get_html()
        assert "Novo&nbsp;parágrafo" in html
        assert "<table><tr><td>célula</td></tr></table>" in html

        # salvar e reler
        assert app.save() is True
        salvo = alvo.read_text(encoding="utf-8")
        assert "Novo&nbsp;parágrafo" in salvo

        # alternância de modos
        app.set_mode("code")
        assert app.mode == "code"
        app.set_mode("design")
        assert app.mode == "design"

        # localizar
        app.find_panel.find_var.set("Parágrafo")
        app.find_next()
        assert app.text.get("sel.first", "sel.last") == "Parágrafo"

        # histórico do modo Design
        app.text.insert("end", " X")
        app._capture_history()
        app.text.insert("end", " Y")
        app.undo()
        assert app.text.get("1.0", "end-1c").endswith(" X")
    finally:
        app.destroy()


@requires_tk
def test_abrir_arquivo_cp1252(tmp_path, monkeypatch):
    monkeypatch.setenv("RD5_PAGESTUDIO_DIR", str(tmp_path / "cfg"))
    from ps_gui.app import App

    alvo = tmp_path / "antiga.htm"
    alvo.write_bytes('<meta charset="windows-1252"><body><p>Ação €</p></body>'
                     .encode("cp1252"))

    app = App()
    try:
        assert app.open_file(str(alvo)) is True
        assert app.encoding == "cp1252"
        assert "Ação" in app.text.get("1.0", "end-1c")
        app.save()
        assert "Ação" in alvo.read_bytes().decode("cp1252")
    finally:
        app.destroy()
