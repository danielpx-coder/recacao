"""Aba completa de gerenciamento do catálogo de modelos com filtros, favoritos e precificação."""

import json
from decimal import Decimal
from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QLineEdit,
    QComboBox, QCheckBox, QMessageBox, QDialog, QFormLayout,
    QSpinBox, QTextEdit, QFileDialog, QGroupBox
)
from PySide6.QtCore import Qt
from danaurium.persistence.repository import repo
from danaurium.catalog.manager import catalog_manager


class ModelEditDialog(QDialog):
    """Diálogo para cadastro manual ou edição de metadados de modelo."""

    def __init__(self, connection_id: str, model_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.connection_id = connection_id
        self.model_data = model_data or {}
        is_edit = bool(model_data)
        self.setWindowTitle("Editar Modelo do Catálogo" if is_edit else "Cadastrar Modelo Manualmente")
        self.resize(520, 520)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.model_id_edit = QLineEdit(self.model_data.get("model_id", ""))
        self.model_id_edit.setPlaceholderText("ID exato enviado na API (ex: gpt-4o, claude-3-5-sonnet-20241022)")
        if is_edit:
            self.model_id_edit.setReadOnly(True)
        form.addRow("ID Exato da API:", self.model_id_edit)

        self.display_name_edit = QLineEdit(self.model_data.get("display_name", ""))
        form.addRow("Nome Amigável:", self.display_name_edit)

        self.org_edit = QLineEdit(self.model_data.get("organization", ""))
        form.addRow("Organização / Criador:", self.org_edit)

        self.context_spin = QSpinBox()
        self.context_spin.setRange(1000, 2000000)
        self.context_spin.setValue(self.model_data.get("context_window") or 128000)
        form.addRow("Janela de Contexto:", self.context_spin)

        self.max_out_spin = QSpinBox()
        self.max_out_spin.setRange(100, 128000)
        self.max_out_spin.setValue(self.model_data.get("max_output_tokens") or 4096)
        form.addRow("Limite de Saída (Tokens):", self.max_out_spin)

        # Preços
        self.p_in_edit = QLineEdit(self.model_data.get("pricing_prompt") or "")
        self.p_in_edit.setPlaceholderText("Ex: 2.50 ou 0.00 se gratuito (em USD)")
        form.addRow("Preço Entrada (Prompt):", self.p_in_edit)

        self.p_out_edit = QLineEdit(self.model_data.get("pricing_completion") or "")
        self.p_out_edit.setPlaceholderText("Ex: 10.00 ou 0.00 se gratuito (em USD)")
        form.addRow("Preço Saída (Completion):", self.p_out_edit)

        self.unit_combo = QComboBox()
        self.unit_combo.addItems(["per_1m_tokens", "per_1k_tokens", "per_token"])
        cur_u = self.model_data.get("pricing_unit", "per_1m_tokens")
        self.unit_combo.setCurrentText(cur_u)
        form.addRow("Unidade do Preço:", self.unit_combo)

        self.p_source_edit = QLineEdit(self.model_data.get("pricing_source", "Manual"))
        form.addRow("Fonte do Preço:", self.p_source_edit)

        self.cat_combo = QComboBox()
        self.cat_combo.addItems(["Econômico", "Intermediário", "Premium", "Personalizado"])
        self.cat_combo.setCurrentText(self.model_data.get("personal_category", "Intermediário"))
        form.addRow("Categoria Pessoal:", self.cat_combo)

        self.free_check = QCheckBox("Marcar explicitamente como Modelo Gratuito")
        self.free_check.setChecked(bool(self.model_data.get("is_free", False)))
        form.addRow("", self.free_check)

        self.notes_edit = QTextEdit()
        self.notes_edit.setMaximumHeight(70)
        self.notes_edit.setPlainText(self.model_data.get("notes", ""))
        form.addRow("Observações:", self.notes_edit)

        layout.addLayout(form)

        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("Salvar Modelo")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self._save)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        layout.addLayout(btn_box)

    def _save(self):
        m_id = self.model_id_edit.text().strip()
        disp = self.display_name_edit.text().strip() or m_id
        if not m_id:
            QMessageBox.warning(self, "Aviso", "O ID exato da API é obrigatório.")
            return

        is_free = self.free_check.isChecked()
        p_in = self.p_in_edit.text().strip() or ("0.000000" if is_free else None)
        p_out = self.p_out_edit.text().strip() or ("0.000000" if is_free else None)

        record_id = f"{self.connection_id}::{m_id}"
        data = {
            "id": record_id,
            "connection_id": self.connection_id,
            "model_id": m_id,
            "display_name": disp,
            "organization": self.org_edit.text().strip() or "Desconhecida",
            "context_window": self.context_spin.value(),
            "max_output_tokens": self.max_out_spin.value(),
            "pricing_prompt": p_in,
            "pricing_completion": p_out,
            "pricing_unit": self.unit_combo.currentText(),
            "pricing_source": self.p_source_edit.text().strip(),
            "personal_category": self.cat_combo.currentText(),
            "is_free": is_free,
            "notes": self.notes_edit.toPlainText().strip(),
            "is_active": True,
        }
        repo.save_model(data)
        self.accept()


class CatalogTab(QWidget):
    """Aba do Catálogo configurável de modelos com filtros e Modo Somente Gratuitos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Banner de aviso do Modo Somente Gratuitos
        self.free_mode_banner = QGroupBox("Status de Políticas de Custo")
        b_lay = QHBoxLayout(self.free_mode_banner)
        self.strict_free_check = QCheckBox("Ativar Modo 'Somente Gratuitos' (Bloqueia modelos pagos ou sem preço comprovado)")
        self.strict_free_check.toggled.connect(self._toggle_strict_free_mode)
        b_lay.addWidget(self.strict_free_check)
        b_lay.addStretch()
        layout.addWidget(self.free_mode_banner)

        # Barra de Filtros e Busca
        filter_bar = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Buscar modelo por nome, ID ou organização...")
        self.search_input.textChanged.connect(self.refresh_catalog)
        filter_bar.addWidget(self.search_input, 2)

        self.conn_combo = QComboBox()
        self.conn_combo.currentIndexChanged.connect(self.refresh_catalog)
        filter_bar.addWidget(self.conn_combo, 1)

        self.price_filter_combo = QComboBox()
        self.price_filter_combo.addItems(["Todos os Modelos", "Somente Gratuitos", "Somente Pagos", "Preço Desconhecido", "Somente Favoritos"])
        self.price_filter_combo.currentIndexChanged.connect(self.refresh_catalog)
        filter_bar.addWidget(self.price_filter_combo, 1)

        self.cat_filter_combo = QComboBox()
        self.cat_filter_combo.addItems(["Todas as Categorias", "Econômico", "Intermediário", "Premium", "Personalizado"])
        self.cat_filter_combo.currentIndexChanged.connect(self.refresh_catalog)
        filter_bar.addWidget(self.cat_filter_combo, 1)

        layout.addLayout(filter_bar)

        # Tabela do Catálogo
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Fav", "Nome Amigável", "ID da API", "Conexão", "Organização",
            "Entrada ($/1M)", "Saída ($/1M)", "Categoria", "Gratuidade"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(8, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        # Barra inferior de ações
        act_bar = QHBoxLayout()
        self.btn_manual_add = QPushButton("+ Cadastrar Modelo Manualmente")
        self.btn_manual_add.setObjectName("primaryButton")
        self.btn_manual_add.clicked.connect(self._add_manual_model)
        self.btn_edit_model = QPushButton("Editar Modelo")
        self.btn_edit_model.clicked.connect(self._edit_selected_model)
        self.btn_toggle_fav = QPushButton("Alternar Favorito")
        self.btn_toggle_fav.clicked.connect(self._toggle_favorite)
        self.btn_export = QPushButton("Exportar Catálogo...")
        self.btn_export.clicked.connect(self._export_catalog)
        self.btn_import = QPushButton("Importar Catálogo...")
        self.btn_import.clicked.connect(self._import_catalog)

        act_bar.addWidget(self.btn_manual_add)
        act_bar.addWidget(self.btn_edit_model)
        act_bar.addWidget(self.btn_toggle_fav)
        act_bar.addWidget(self.btn_export)
        act_bar.addWidget(self.btn_import)
        act_bar.addStretch()
        layout.addLayout(act_bar)

        self._load_connections_filter()
        self._load_budget_settings()
        self.refresh_catalog()

    def _load_connections_filter(self):
        self.conn_combo.clear()
        self.conn_combo.addItem("Todas as Conexões", None)
        for c in repo.get_all_connections():
            self.conn_combo.addItem(c["name"], c["id"])

    def _load_budget_settings(self):
        settings = repo.get_budget_settings()
        is_strict_free = bool(settings.get("strict_free_mode", False))
        self.strict_free_check.setChecked(is_strict_free)

    def _toggle_strict_free_mode(self, checked: bool):
        settings = repo.get_budget_settings()
        settings["strict_free_mode"] = checked
        repo.update_budget_settings(settings)
        self.refresh_catalog()

    def refresh_catalog(self):
        query = self.search_input.text().strip() or None
        conn_id = self.conn_combo.currentData()
        price_filter = self.price_filter_combo.currentText()
        cat_filter = self.cat_filter_combo.currentText()

        is_free = None
        only_fav = False
        if price_filter == "Somente Gratuitos":
            is_free = True
        elif price_filter == "Somente Pagos":
            is_free = False
        elif price_filter == "Somente Favoritos":
            only_fav = True

        category = None if cat_filter == "Todas as Categorias" else cat_filter

        models = repo.get_models(
            connection_id=conn_id,
            only_active=True,
            is_free=is_free,
            only_favorites=only_fav,
            personal_category=category,
            search_query=query,
        )

        # Se filtro for preço desconhecido
        if price_filter == "Preço Desconhecido":
            models = [m for m in models if m.get("pricing_prompt") is None and not m.get("is_free")]

        conns_map = {c["id"]: c["name"] for c in repo.get_all_connections()}

        self.table.setRowCount(len(models))
        for r_idx, m in enumerate(models):
            fav_icon = "★" if m.get("is_favorite") else "☆"
            conn_name = conns_map.get(m["connection_id"], m["connection_id"])

            p_in = f"${m['pricing_prompt']}" if m.get("pricing_prompt") is not None else "Desconhecido"
            p_out = f"${m['pricing_completion']}" if m.get("pricing_completion") is not None else "Desconhecido"

            free_label = "Gratuito" if m.get("is_free") else ("Pago" if p_in != "Desconhecido" else "Desconhecido")

            self.table.setItem(r_idx, 0, QTableWidgetItem(fav_icon))
            self.table.setItem(r_idx, 1, QTableWidgetItem(m["display_name"]))
            self.table.setItem(r_idx, 2, QTableWidgetItem(m["model_id"]))
            self.table.setItem(r_idx, 3, QTableWidgetItem(conn_name))
            self.table.setItem(r_idx, 4, QTableWidgetItem(m.get("organization") or "-"))
            self.table.setItem(r_idx, 5, QTableWidgetItem(p_in))
            self.table.setItem(r_idx, 6, QTableWidgetItem(p_out))
            self.table.setItem(r_idx, 7, QTableWidgetItem(m.get("personal_category", "Intermediário")))
            self.table.setItem(r_idx, 8, QTableWidgetItem(free_label))

            self.table.item(r_idx, 1).setData(Qt.UserRole, m)

    def _get_selected_model(self) -> Optional[Dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Aviso", "Selecione um modelo na tabela.")
            return None
        return self.table.item(row, 1).data(Qt.UserRole)

    def _add_manual_model(self):
        conns = repo.get_all_connections()
        if not conns:
            QMessageBox.warning(self, "Aviso", "Cadastre primeiro uma conexão antes de adicionar modelos.")
            return

        conn_id = conns[0]["id"]
        dlg = ModelEditDialog(connection_id=conn_id, parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_catalog()

    def _edit_selected_model(self):
        m = self._get_selected_model()
        if m:
            dlg = ModelEditDialog(connection_id=m["connection_id"], model_data=m, parent=self)
            if dlg.exec() == QDialog.Accepted:
                self.refresh_catalog()

    def _toggle_favorite(self):
        m = self._get_selected_model()
        if m:
            new_fav = not bool(m.get("is_favorite", False))
            repo.update_model_preferences(m["id"], is_favorite=new_fav)
            self.refresh_catalog()

    def _export_catalog(self):
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar Configurações de Catálogo",
            "catalogo_modelos.json",
            "Arquivos JSON (*.json)",
        )
        if file_path:
            try:
                json_data = catalog_manager.export_catalog_json()
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(json_data)
                QMessageBox.information(self, "Exportação Concluída", "Configurações de catálogo exportadas com sucesso (livres de chaves e segredos).")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao exportar catálogo: {e}")

    def _import_catalog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar Configurações de Catálogo",
            "",
            "Arquivos JSON (*.json)",
        )
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                count = catalog_manager.import_catalog_json(content)
                self.refresh_catalog()
                QMessageBox.information(self, "Importação Concluída", f"{count} registros de modelos importados com sucesso.")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao importar catálogo: {e}")
