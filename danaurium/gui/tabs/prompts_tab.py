"""Aba da biblioteca de instruções e prompts editoriais reutilizáveis e versionados."""

from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QMessageBox,
    QDialog, QFormLayout, QLineEdit, QComboBox, QTextEdit
)
from PySide6.QtCore import Qt
from danaurium.persistence.repository import repo
from danaurium.editorial.prompts_library import get_all_prompts


class PromptEditDialog(QDialog):
    """Diálogo para adicionar ou editar um prompt da biblioteca."""

    def __init__(self, prompt_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.prompt_data = prompt_data or {}
        is_edit = bool(prompt_data)
        self.setWindowTitle("Editar Instrução Editorial" if is_edit else "Nova Instrução Editorial")
        self.resize(500, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit(self.prompt_data.get("title", ""))
        form.addRow("Título da Instrução:", self.title_edit)

        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["Edição", "Redação", "Estilo", "Redes Sociais", "Checagem", "Geral"])
        self.cat_combo.setCurrentText(self.prompt_data.get("category", "Edição"))
        form.addRow("Categoria:", self.cat_combo)

        self.content_edit = QTextEdit()
        self.content_edit.setPlainText(self.prompt_data.get("content", ""))
        self.content_edit.setPlaceholderText("Escreva a instrução que será aplicada aos textos ou trechos...")
        form.addRow("Texto da Instrução:", self.content_edit)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("Salvar Instrução")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self._save)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        layout.addLayout(btn_box)

    def _save(self):
        title = self.title_edit.text().strip()
        content = self.content_edit.toPlainText().strip()
        if not title or not content:
            QMessageBox.warning(self, "Aviso", "Título e conteúdo da instrução são obrigatórios.")
            return

        import time
        p_id = self.prompt_data.get("id") or f"prompt_{int(time.time()*1000)}"
        ver = (self.prompt_data.get("version") or 0) + 1

        with repo.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO prompt_library (id, title, category, content, version, is_default, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, 0, datetime('now'), datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    category = excluded.category,
                    content = excluded.content,
                    version = excluded.version,
                    updated_at = datetime('now')
            """, (p_id, title, self.cat_combo.currentText(), content, ver))
            conn.commit()

        self.accept()


class PromptsTab(QWidget):
    """Aba da biblioteca de instruções editoriais."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("<b>Biblioteca de Instruções Editoriais Reutilizáveis</b>"))
        top_bar.addStretch()

        self.btn_add = QPushButton("+ Nova Instrução")
        self.btn_add.setObjectName("primaryButton")
        self.btn_add.clicked.connect(self._add_prompt)
        top_bar.addWidget(self.btn_add)
        layout.addLayout(top_bar)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Categoria", "Título", "Versão", "Conteúdo da Instrução"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        act_bar = QHBoxLayout()
        self.btn_edit = QPushButton("Editar")
        self.btn_edit.clicked.connect(self._edit_prompt)
        self.btn_del = QPushButton("Excluir")
        self.btn_del.clicked.connect(self._delete_prompt)

        act_bar.addWidget(self.btn_edit)
        act_bar.addWidget(self.btn_del)
        act_bar.addStretch()
        layout.addLayout(act_bar)

        self.refresh_prompts()

    def refresh_prompts(self):
        prompts = get_all_prompts(repo)
        self.table.setRowCount(len(prompts))
        for r_idx, p in enumerate(prompts):
            self.table.setItem(r_idx, 0, QTableWidgetItem(p["category"]))
            self.table.setItem(r_idx, 1, QTableWidgetItem(p["title"]))
            self.table.setItem(r_idx, 2, QTableWidgetItem(f"v{p.get('version', 1)}"))
            self.table.setItem(r_idx, 3, QTableWidgetItem(p["content"][:120] + "..."))
            self.table.item(r_idx, 1).setData(Qt.UserRole, p)

    def _get_selected_prompt(self) -> Optional[Dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Aviso", "Selecione uma instrução na lista.")
            return None
        return self.table.item(row, 1).data(Qt.UserRole)

    def _add_prompt(self):
        dlg = PromptEditDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_prompts()

    def _edit_prompt(self):
        p = self._get_selected_prompt()
        if p:
            dlg = PromptEditDialog(prompt_data=p, parent=self)
            if dlg.exec() == QDialog.Accepted:
                self.refresh_prompts()

    def _delete_prompt(self):
        p = self._get_selected_prompt()
        if p:
            confirm = QMessageBox.question(
                self,
                "Confirmar Exclusão",
                f"Deseja excluir a instrução '{p['title']}'?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm == QMessageBox.Yes:
                with repo.db.get_connection() as conn:
                    conn.execute("DELETE FROM prompt_library WHERE id = ?", (p["id"],))
                    conn.commit()
                self.refresh_prompts()
