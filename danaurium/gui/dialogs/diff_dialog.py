"""Diálogo de comparação visual (diff) entre versões de um mesmo produto editorial."""

import difflib
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextBrowser,
    QPushButton, QComboBox, QSplitter
)
from PySide6.QtCore import Qt


class VersionDiffDialog(QDialog):
    """Compara visualmente duas versões de um produto editorial com destaque de alterações."""

    def __init__(self, versions: list, current_ver_index: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Comparação Visual entre Versões")
        self.resize(850, 550)
        self.versions = versions

        layout = QVBoxLayout(self)

        # Barra superior com seletores de versão
        sel_layout = QHBoxLayout()
        sel_layout.addWidget(QLabel("<b>Comparar Versão:</b>"))
        self.combo_v1 = QComboBox()
        self.combo_v2 = QComboBox()

        for v in versions:
            label = f"Versão {v['version_number']} ({v.get('created_at', '')[:16]} - {v.get('char_count', 0)} caracteres)"
            self.combo_v1.addItem(label, v)
            self.combo_v2.addItem(label, v)

        if len(versions) >= 2:
            self.combo_v1.setCurrentIndex(1)
            self.combo_v2.setCurrentIndex(0)
        elif len(versions) == 1:
            self.combo_v1.setCurrentIndex(0)
            self.combo_v2.setCurrentIndex(0)

        self.combo_v1.currentIndexChanged.connect(self._render_diff)
        self.combo_v2.currentIndexChanged.connect(self._render_diff)

        sel_layout.addWidget(self.combo_v1)
        sel_layout.addWidget(QLabel("<b>com a Versão:</b>"))
        sel_layout.addWidget(self.combo_v2)
        sel_layout.addStretch()
        layout.addLayout(sel_layout)

        # Área de visualização dividida
        splitter = QSplitter(Qt.Horizontal)
        self.view_v1 = QTextBrowser()
        self.view_v2 = QTextBrowser()

        splitter.addWidget(self.view_v1)
        splitter.addWidget(self.view_v2)
        layout.addWidget(splitter, 1)

        # Botão fechar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton("Fechar")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

        self._render_diff()

    def _render_diff(self):
        v1 = self.combo_v1.currentData()
        v2 = self.combo_v2.currentData()
        if not v1 or not v2:
            return

        text1 = v1.get("content", "")
        text2 = v2.get("content", "")

        lines1 = text1.splitlines(keepends=True)
        lines2 = text2.splitlines(keepends=True)

        d = difflib.Differ()
        diff = list(d.compare(lines1, lines2))

        html1 = ["<div style='font-family: monospace; font-size: 13px;'>"]
        html2 = ["<div style='font-family: monospace; font-size: 13px;'>"]

        for line in diff:
            code = line[:2]
            content = line[2:].replace("<", "&lt;").replace(">", "&gt;")
            if not content.strip():
                content = "&nbsp;"

            if code == "  ":  # Inalterado
                html1.append(f"<div style='color: #495057;'>{content}</div>")
                html2.append(f"<div style='color: #495057;'>{content}</div>")
            elif code == "- ":  # Removido na nova versão
                html1.append(f"<div style='background-color: #FFE3E3; color: #C92A2A;'>- {content}</div>")
            elif code == "+ ":  # Adicionado na nova versão
                html2.append(f"<div style='background-color: #D3F9D8; color: #2B8A3E;'>+ {content}</div>")

        html1.append("</div>")
        html2.append("</div>")

        self.view_v1.setHtml("\n".join(html1))
        self.view_v2.setHtml("\n".join(html2))
