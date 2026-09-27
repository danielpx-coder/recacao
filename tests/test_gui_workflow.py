"""Testes automatizados da interface gráfica PySide6 (execução em modo offscreen)."""

import os
import pytest
from PySide6.QtWidgets import QApplication

# Garantir QApplication única para a sessão de testes
@pytest.fixture(scope="session")
def qapp():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


def test_main_window_tabs_and_workflow(qapp, isolated_app_environment):
    from danaurium.gui.main_window import MainWindow

    window = MainWindow()
    assert window.tabs.count() == 6

    # 1. Testar aba Bancada de Redação
    editor = window.tab_editor
    editor.title_input.setText("Projeto Teste GUI")
    sample_story = (
        "O Ministério da Educação anunciou nesta terça-feira R$ 450 milhões para 12.500 escolas.\n\n"
        'O ministro afirmou: "A inclusão digital é inegociável".'
    )
    editor.source_editor.setPlainText(sample_story)

    # 2. Extrair fatos da matéria
    editor._extract_facts()
    assert editor.facts_table.rowCount() >= 2
    pinned = editor._get_pinned_facts()
    assert len(pinned) >= 2

    # 3. Testar auto-salvamento
    editor._auto_save()
    repo = isolated_app_environment["repo"]
    proj = repo.get_project(editor.current_project_id)
    assert proj is not None
    assert proj["title"] == "Projeto Teste GUI"

    # 4. Navegar entre as abas e validar inicialização
    for idx in range(window.tabs.count()):
        window.tabs.setCurrentIndex(idx)
        assert window.tabs.currentIndex() == idx

    # 5. Fechar janela com segurança
    window.close()
