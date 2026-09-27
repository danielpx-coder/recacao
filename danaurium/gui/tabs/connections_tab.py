"""Aba de gerenciamento de conexões, provedores, chaves e testes de diagnóstico."""

from typing import Dict, Any, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QDialog,
    QFormLayout, QLineEdit, QComboBox, QSpinBox, QMessageBox,
    QGroupBox, QTextBrowser, QCheckBox
)
from PySide6.QtCore import Qt
from danaurium.persistence.repository import repo
from danaurium.security.keyring_manager import credentials, extract_domain
from danaurium.gui.workers import ConnectionTestWorker, CatalogSyncWorker

DEFAULT_PROVIDERS = {
    "OpenAI": {
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "catalog_path": "/models",
        "generation_path": "/chat/completions",
    },
    "Anthropic": {
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "catalog_path": "/models",
        "generation_path": "/messages",
    },
    "OpenRouter": {
        "provider_type": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "catalog_path": "/models",
        "generation_path": "/chat/completions",
    },
    "Personalizado (Compatível OpenAI)": {
        "provider_type": "custom_openai",
        "base_url": "http://localhost:11434/v1",
        "catalog_path": "/models",
        "generation_path": "/chat/completions",
    },
}


class ConnectionEditDialog(QDialog):
    """Diálogo completo para criação e edição de uma conexão com validação de domínio."""

    def __init__(self, connection_data: Optional[Dict[str, Any]] = None, parent=None):
        super().__init__(parent)
        self.connection_data = connection_data or {}
        is_edit = bool(connection_data)
        self.setWindowTitle("Editar Conexão" if is_edit else "Nova Conexão")
        self.resize(540, 480)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name_edit = QLineEdit(self.connection_data.get("name", "Nova Conexão"))
        form.addRow("Nome da Conexão:", self.name_edit)

        self.provider_combo = QComboBox()
        for p_name in DEFAULT_PROVIDERS:
            self.provider_combo.addItem(p_name)
        
        # Selecionar tipo existente
        p_type = self.connection_data.get("provider_type", "openai")
        for idx, p_name in enumerate(DEFAULT_PROVIDERS):
            if DEFAULT_PROVIDERS[p_name]["provider_type"] == p_type:
                self.provider_combo.setCurrentIndex(idx)
                break
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("Provedor e Protocolo:", self.provider_combo)

        self.url_edit = QLineEdit(self.connection_data.get("base_url", "https://api.openai.com/v1"))
        form.addRow("URL-base:", self.url_edit)

        # Chave de API
        key_layout = QHBoxLayout()
        self.key_edit = QLineEdit()
        self.key_edit.setEchoMode(QLineEdit.Password)
        self.key_edit.setPlaceholderText("Deixe em branco para manter a chave já salva no cofre" if is_edit else "Cole sua chave de API aqui")
        self.btn_toggle_key = QPushButton("Mostrar")
        self.btn_toggle_key.setFixedWidth(70)
        self.btn_toggle_key.clicked.connect(self._toggle_key_visibility)
        key_layout.addWidget(self.key_edit)
        key_layout.addWidget(self.btn_toggle_key)
        form.addRow("Chave de API (Segredo):", key_layout)

        # Caminhos normalizados
        self.catalog_path_edit = QLineEdit(self.connection_data.get("catalog_path", "/models"))
        form.addRow("Caminho do Catálogo:", self.catalog_path_edit)

        self.generation_path_edit = QLineEdit(self.connection_data.get("generation_path", "/chat/completions"))
        form.addRow("Caminho de Geração:", self.generation_path_edit)

        self.timeout_spin = QSpinBox()
        self.timeout_spin.setRange(10, 300)
        self.timeout_spin.setValue(self.connection_data.get("timeout_seconds", 60))
        self.timeout_spin.setSuffix(" segundos")
        form.addRow("Tempo Limite:", self.timeout_spin)

        self.retries_spin = QSpinBox()
        self.retries_spin.setRange(0, 10)
        self.retries_spin.setValue(self.connection_data.get("max_retries", 3))
        form.addRow("Política de Repetição (Retries):", self.retries_spin)

        self.active_check = QCheckBox("Conexão Ativa")
        self.active_check.setChecked(bool(self.connection_data.get("is_active", True)))
        form.addRow("", self.active_check)

        layout.addLayout(form)

        # Explicação de segurança
        storage_mode = credentials.get_storage_mode_name()
        info_label = QLabel(f"<i>Armazenamento seguro ativo: {storage_mode}. As chaves jamais são salvas no banco de dados SQLite ou em arquivos de log.</i>")
        info_label.setStyleSheet("color: #495057; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # Botões
        btn_box = QHBoxLayout()
        btn_box.addStretch()
        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_save = QPushButton("Salvar Conexão")
        self.btn_save.setObjectName("primaryButton")
        self.btn_save.clicked.connect(self._save_connection)
        btn_box.addWidget(self.btn_cancel)
        btn_box.addWidget(self.btn_save)
        layout.addLayout(btn_box)

    def _toggle_key_visibility(self):
        if self.key_edit.echoMode() == QLineEdit.Password:
            self.key_edit.setEchoMode(QLineEdit.Normal)
            self.btn_toggle_key.setText("Ocultar")
        else:
            self.key_edit.setEchoMode(QLineEdit.Password)
            self.btn_toggle_key.setText("Mostrar")

    def _on_provider_changed(self):
        selected_text = self.provider_combo.currentText()
        preset = DEFAULT_PROVIDERS.get(selected_text)
        if preset:
            self.url_edit.setText(preset["base_url"])
            self.catalog_path_edit.setText(preset["catalog_path"])
            self.generation_path_edit.setText(preset["generation_path"])

    def _save_connection(self):
        name = self.name_edit.text().strip()
        url = self.url_edit.text().strip()
        if not name or not url:
            QMessageBox.warning(self, "Aviso", "Nome da conexão e URL-base são campos obrigatórios.")
            return

        selected_text = self.provider_combo.currentText()
        provider_type = DEFAULT_PROVIDERS[selected_text]["provider_type"]

        conn_id = self.connection_data.get("id") or f"conn_{selected_text.lower().replace(' ', '_')[:10]}"
        old_url = self.connection_data.get("base_url")

        new_key = self.key_edit.text().strip()

        # Proteção de domínio: se a URL mudou de host e nenhuma nova chave foi digitada
        if old_url and extract_domain(old_url) != extract_domain(url) and not new_key:
            old_key = credentials.get_api_key(conn_id, old_url)
            if old_key:
                confirm = QMessageBox.question(
                    self,
                    "Confirmação de Segurança de Domínio",
                    f"O domínio da conexão mudou de '{extract_domain(old_url)}' para '{extract_domain(url)}'. "
                    "Deseja vincular explicitamente a chave existente ao novo domínio?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if confirm == QMessageBox.Yes:
                    credentials.set_api_key(conn_id, url, old_key)
                else:
                    return

        # Salvar metadados no SQLite
        data = {
            "id": conn_id,
            "name": name,
            "provider_type": provider_type,
            "base_url": url,
            "catalog_path": self.catalog_path_edit.text().strip(),
            "generation_path": self.generation_path_edit.text().strip(),
            "timeout_seconds": self.timeout_spin.value(),
            "max_retries": self.retries_spin.value(),
            "is_active": self.active_check.isChecked(),
        }
        repo.save_connection(data)

        # Salvar chave de API com segurança caso informada
        if new_key:
            credentials.set_api_key(conn_id, url, new_key)

        self.accept()


class ConnectionsTab(QWidget):
    """Aba central de conexões com ações de teste, diagnóstico e atualização de catálogo."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_workers = []

        layout = QVBoxLayout(self)

        # Cabeçalho com ações
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel("<b>Conexões de Provedores de IA</b>"))
        top_bar.addStretch()

        self.btn_add = QPushButton("+ Nova Conexão")
        self.btn_add.setObjectName("primaryButton")
        self.btn_add.clicked.connect(self._add_connection)
        top_bar.addWidget(self.btn_add)
        layout.addLayout(top_bar)

        # Tabela de conexões
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Nome", "Provedor", "URL-Base", "Geração", "Timeout", "Chave Configurada", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        # Botões de ação sobre a linha selecionada
        act_bar = QHBoxLayout()
        self.btn_test = QPushButton("Testar Conexão")
        self.btn_test.clicked.connect(self._test_selected_connection)
        self.btn_sync = QPushButton("Atualizar Catálogo")
        self.btn_sync.clicked.connect(self._sync_selected_catalog)
        self.btn_edit = QPushButton("Editar Conexão")
        self.btn_edit.clicked.connect(self._edit_selected_connection)
        self.btn_del = QPushButton("Excluir Conexão")
        self.btn_del.clicked.connect(self._delete_selected_connection)

        act_bar.addWidget(self.btn_test)
        act_bar.addWidget(self.btn_sync)
        act_bar.addWidget(self.btn_edit)
        act_bar.addWidget(self.btn_del)
        act_bar.addStretch()
        layout.addLayout(act_bar)

        # Painel de diagnóstico compreensível
        grp_diag = QGroupBox("Diagnóstico da Conexão Selecionada")
        d_lay = QVBoxLayout(grp_diag)
        self.diag_browser = QTextBrowser()
        self.diag_browser.setMaximumHeight(140)
        self.diag_browser.setPlaceholderText("Selecione uma conexão e clique em 'Testar Conexão' para visualizar diagnósticos de latência, códigos HTTP e permissões.")
        d_lay.addWidget(self.diag_browser)
        layout.addWidget(grp_diag)

        self._seed_default_connections()
        self.refresh_connections()

    def _seed_default_connections(self):
        """Inicializa conexões padrão caso a tabela esteja vazia."""
        existing = repo.get_all_connections()
        if not existing:
            # Cadastrar conexões de ponto de partida recomendadas
            repo.save_connection({
                "id": "conn_openai",
                "name": "OpenAI Oficial",
                "provider_type": "openai",
                "base_url": "https://api.openai.com/v1",
                "catalog_path": "/models",
                "generation_path": "/chat/completions",
                "timeout_seconds": 60,
                "max_retries": 3,
                "is_active": True,
            })
            repo.save_connection({
                "id": "conn_anthropic",
                "name": "Anthropic Claude",
                "provider_type": "anthropic",
                "base_url": "https://api.anthropic.com/v1",
                "catalog_path": "/models",
                "generation_path": "/messages",
                "timeout_seconds": 60,
                "max_retries": 3,
                "is_active": True,
            })
            repo.save_connection({
                "id": "conn_openrouter",
                "name": "OpenRouter",
                "provider_type": "openrouter",
                "base_url": "https://openrouter.ai/api/v1",
                "catalog_path": "/models",
                "generation_path": "/chat/completions",
                "timeout_seconds": 60,
                "max_retries": 3,
                "is_active": True,
            })

    def refresh_connections(self):
        conns = repo.get_all_connections()
        self.table.setRowCount(len(conns))
        for r_idx, c in enumerate(conns):
            conn_id = c["id"]
            has_key = bool(credentials.get_api_key(conn_id, c["base_url"]))

            self.table.setItem(r_idx, 0, QTableWidgetItem(c["name"]))
            self.table.setItem(r_idx, 1, QTableWidgetItem(c["provider_type"].upper()))
            self.table.setItem(r_idx, 2, QTableWidgetItem(c["base_url"]))
            self.table.setItem(r_idx, 3, QTableWidgetItem(c["generation_path"]))
            self.table.setItem(r_idx, 4, QTableWidgetItem(f"{c['timeout_seconds']}s"))
            self.table.setItem(r_idx, 5, QTableWidgetItem("Sim (Protegida)" if has_key else "Não"))
            self.table.setItem(r_idx, 6, QTableWidgetItem("Ativa" if c.get("is_active") else "Inativa"))

            # Guardar dict da conexão no item
            self.table.item(r_idx, 0).setData(Qt.UserRole, c)

    def _get_selected_connection(self) -> Optional[Dict[str, Any]]:
        row = self.table.currentRow()
        if row < 0:
            QMessageBox.information(self, "Aviso", "Selecione uma conexão na tabela.")
            return None
        return self.table.item(row, 0).data(Qt.UserRole)

    def _add_connection(self):
        dlg = ConnectionEditDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            self.refresh_connections()

    def _edit_selected_connection(self):
        conn = self._get_selected_connection()
        if conn:
            dlg = ConnectionEditDialog(connection_data=conn, parent=self)
            if dlg.exec() == QDialog.Accepted:
                self.refresh_connections()

    def _delete_selected_connection(self):
        conn = self._get_selected_connection()
        if conn:
            confirm = QMessageBox.question(
                self,
                "Confirmar Exclusão",
                f"Deseja excluir a conexão '{conn['name']}'? Os modelos associados também serão removidos.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm == QMessageBox.Yes:
                repo.delete_connection(conn["id"])
                credentials.delete_api_key(conn["id"])
                self.refresh_connections()

    def _test_selected_connection(self):
        conn = self._get_selected_connection()
        if not conn:
            return

        self.btn_test.setEnabled(False)
        self.diag_browser.setHtml(f"<i>Executando teste de conexão com {conn['name']}...</i>")

        worker = ConnectionTestWorker(conn, self)
        worker.finished.connect(lambda res: self._on_test_finished(conn, res, worker))
        self.active_workers.append(worker)
        worker.start()

    def _on_test_finished(self, conn: Dict[str, Any], res: Dict[str, Any], worker: ConnectionTestWorker):
        self.btn_test.setEnabled(True)
        if worker in self.active_workers:
            self.active_workers.remove(worker)

        status_color = "#2B8A3E" if res["success"] else "#C92A2A"
        icon = "✔" if res["success"] else "✖"

        html_report = f"""
        <div style='font-size: 13px;'>
            <b style='color: {status_color}; font-size: 14px;'>{icon} {res['message']}</b><br>
            <b>Conexão:</b> {conn['name']} ({conn['provider_type'].upper()})<br>
            <b>URL Testada:</b> {conn['base_url']}{conn['catalog_path']}<br>
            <b>Latência:</b> {res['latency_ms']} ms | <b>Status HTTP:</b> {res['status_code'] or 'Falha de rede/timeout'}<br>
            <b>Detalhes do Diagnóstico:</b> {res['details']}
        </div>
        """
        self.diag_browser.setHtml(html_report)

    def _sync_selected_catalog(self):
        conn = self._get_selected_connection()
        if not conn:
            return

        self.btn_sync.setEnabled(False)
        self.diag_browser.setHtml(f"<i>Consultando e sincronizando catálogo de {conn['name']}...</i>")

        worker = CatalogSyncWorker(conn["id"], self)
        worker.finished.connect(lambda count, msg: self._on_sync_finished(count, msg, worker))
        self.active_workers.append(worker)
        worker.start()

    def _on_sync_finished(self, count: int, msg: str, worker: CatalogSyncWorker):
        self.btn_sync.setEnabled(True)
        if worker in self.active_workers:
            self.active_workers.remove(worker)

        QMessageBox.information(self, "Catálogo Atualizado", msg)
        self.diag_browser.setHtml(f"<b style='color: #2B8A3E;'>Catálogo sincronizado:</b> {msg}")
