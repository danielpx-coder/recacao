"""Diálogo para reescrita e refinamento de trechos selecionados com instruções rápidas."""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QRadioButton, QButtonGroup, QLineEdit
)
from PySide6.QtCore import Qt


class RewriteSelectionDialog(QDialog):
    """Permite ao jornalista pedir refinamento editorial de um trecho selecionado."""

    def __init__(self, selected_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Reescrever / Refinar Trecho")
        self.resize(500, 380)
        self.selected_text = selected_text
        self.instruction_result = ""

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("<b>Trecho Selecionado:</b>"))
        self.preview_edit = QTextEdit()
        self.preview_edit.setPlainText(selected_text)
        self.preview_edit.setReadOnly(True)
        self.preview_edit.setMaximumHeight(90)
        layout.addWidget(self.preview_edit)

        layout.addWidget(QLabel("<b>Ação Editorial Desejada:</b>"))
        self.btn_group = QButtonGroup(self)

        self.rb_encurtar = QRadioButton("Encurtar (manter dados e eliminar redundâncias)")
        self.rb_simplificar = QRadioButton("Simplificar (remover jargões e tornar acessível)")
        self.rb_mais_direto = QRadioButton("Tornar mais direto (ordem direta e frases ativas)")
        self.rb_custom = QRadioButton("Instrução personalizada:")

        self.rb_encurtar.setChecked(True)

        self.btn_group.addButton(self.rb_encurtar, 1)
        self.btn_group.addButton(self.rb_simplificar, 2)
        self.btn_group.addButton(self.rb_mais_direto, 3)
        self.btn_group.addButton(self.rb_custom, 4)

        layout.addWidget(self.rb_encurtar)
        layout.addWidget(self.rb_simplificar)
        layout.addWidget(self.rb_mais_direto)
        layout.addWidget(self.rb_custom)

        self.custom_input = QLineEdit()
        self.custom_input.setPlaceholderText("Ex: Reescreva com tom mais urgente ou enfatize os prazos...")
        self.custom_input.setEnabled(False)
        self.rb_custom.toggled.connect(self.custom_input.setEnabled)
        layout.addWidget(self.custom_input)

        # Botões de confirmação
        btn_layout = QHBoxLayout()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_ok = QPushButton("Aplicar Reescrita")
        self.btn_ok.setObjectName("primaryButton")
        self.btn_ok.clicked.connect(self._on_confirm)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_ok)
        layout.addLayout(btn_layout)

    def _on_confirm(self):
        checked_id = self.btn_group.checkedId()
        if checked_id == 1:
            self.instruction_result = "Encurte o trecho selecionado eliminando palavras vazias e mantendo todos os dados e nomes essenciais."
        elif checked_id == 2:
            self.instruction_result = "Simplifique a linguagem do trecho selecionado, substituindo termos técnicos por vocabulário acessível ao público geral."
        elif checked_id == 3:
            self.instruction_result = "Reescreva o trecho na ordem direta estrita (sujeito-verbo-objeto) com verbos ativos e frases curtas."
        elif checked_id == 4:
            self.instruction_result = self.custom_input.text().strip() or "Refine o trecho selecionado."

        self.accept()

    def get_instruction(self) -> str:
        return self.instruction_result
