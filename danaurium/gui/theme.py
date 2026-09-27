"""Tema visual profissional, moderno e sóbrio em padrão claro para PySide6."""

LIGHT_THEME_QSS = """
/* Danaurium Redação Studio - Tema Claro Profissional */

QWidget {
    background-color: #F8F9FA;
    color: #212529;
    font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, 'Roboto', 'Helvetica Neue', Arial, sans-serif;
    font-size: 13px;
}

/* Janela Principal e Abas */
QMainWindow {
    background-color: #F1F3F5;
}

QTabWidget::pane {
    border: 1px solid #CED4DA;
    background-color: #FFFFFF;
    border-radius: 4px;
    top: -1px;
}

QTabBar::tab {
    background-color: #E9ECEF;
    color: #495057;
    padding: 9px 18px;
    margin-right: 3px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    border: 1px solid #CED4DA;
    border-bottom: none;
    font-weight: 500;
}

QTabBar::tab:selected {
    background-color: #FFFFFF;
    color: #0B7285;
    border-bottom: 2px solid #0B7285;
    font-weight: bold;
}

QTabBar::tab:hover:!selected {
    background-color: #DEE2E6;
}

/* Painéis e Caixas de Grupo */
QGroupBox {
    background-color: #FFFFFF;
    border: 1px solid #DEE2E6;
    border-radius: 6px;
    margin-top: 14px;
    padding-top: 16px;
    font-weight: 600;
    color: #343A40;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 2px 8px;
    background-color: #FFFFFF;
    color: #0B7285;
}

/* Entradas de Texto */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QComboBox {
    background-color: #FFFFFF;
    border: 1px solid #CED4DA;
    border-radius: 4px;
    padding: 6px 10px;
    color: #212529;
    selection-background-color: #0B7285;
    selection-color: #FFFFFF;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus {
    border: 1px solid #0B7285;
    background-color: #FFFFFF;
}

/* Botões */
QPushButton {
    background-color: #E9ECEF;
    color: #212529;
    border: 1px solid #CED4DA;
    border-radius: 4px;
    padding: 7px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #DEE2E6;
    border-color: #ADB5BD;
}

QPushButton:pressed {
    background-color: #CED4DA;
}

QPushButton:disabled {
    background-color: #F1F3F5;
    color: #ADB5BD;
    border-color: #E9ECEF;
}

/* Botão de Ação Primária (Geração) */
QPushButton#primaryButton {
    background-color: #0B7285;
    color: #FFFFFF;
    border: 1px solid #085666;
    font-weight: bold;
}

QPushButton#primaryButton:hover {
    background-color: #0C8599;
}

QPushButton#primaryButton:pressed {
    background-color: #096172;
}

/* Botão de Cancelamento */
QPushButton#dangerButton {
    background-color: #FA5252;
    color: #FFFFFF;
    border: 1px solid #E03131;
}

QPushButton#dangerButton:hover {
    background-color: #F03E3E;
}

/* Tabelas e Listas */
QTableWidget, QTableView, QListWidget, QTreeWidget {
    background-color: #FFFFFF;
    border: 1px solid #DEE2E6;
    gridline-color: #F1F3F5;
    border-radius: 4px;
    alternate-background-color: #F8F9FA;
}

QHeaderView::section {
    background-color: #E9ECEF;
    color: #495057;
    padding: 6px 8px;
    border: none;
    border-right: 1px solid #DEE2E6;
    border-bottom: 1px solid #CED4DA;
    font-weight: 600;
}

/* Barras de Rolagem */
QScrollBar:vertical {
    border: none;
    background: #F1F3F5;
    width: 8px;
    margin: 0px;
}

QScrollBar::handle:vertical {
    background: #CED4DA;
    min-height: 25px;
    border-radius: 4px;
}

QScrollBar::handle:vertical:hover {
    background: #ADB5BD;
}

/* Barra de Status */
QStatusBar {
    background-color: #E9ECEF;
    color: #495057;
    border-top: 1px solid #CED4DA;
    padding: 3px 6px;
    font-size: 12px;
}

/* Badges e Rótulos Especiais */
QLabel#charCountBadge {
    padding: 3px 8px;
    border-radius: 10px;
    font-weight: bold;
    font-size: 11px;
}

QLabel#statusOk {
    color: #2B8A3E;
    font-weight: bold;
}

QLabel#statusWarn {
    color: #F08C00;
    font-weight: bold;
}

QLabel#statusError {
    color: #C92A2A;
    font-weight: bold;
}
"""
