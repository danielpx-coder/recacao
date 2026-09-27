"""Ponto de entrada principal da aplicação Danaurium Redação Studio."""

import os
import sys
import logging
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from danaurium import __app_name__
from danaurium.config import setup_logging, paths
from danaurium.gui.theme import LIGHT_THEME_QSS
from danaurium.gui.main_window import MainWindow

logger = logging.getLogger("danaurium.app")


def main():
    """Inicializa configurações, aplica tema visual e abre a janela principal."""
    setup_logging()
    logger.info("Iniciando %s...", __app_name__)

    # Configuração de renderização de fontes e DPI no Windows 10/11
    if hasattr(Qt, "AA_EnableHighDpiScaling"):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, "AA_UseHighDpiPixmaps"):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName(__app_name__)
    app.setStyleSheet(LIGHT_THEME_QSS)

    window = MainWindow()
    window.show()

    logger.info("Interface desktop carregada com sucesso.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
