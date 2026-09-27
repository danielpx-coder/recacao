"""Janela principal do aplicativo Danaurium Redação Studio."""

import sys
from PySide6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar, QLabel, QMenuBar,
    QMenu, QMessageBox, QApplication, QWidget, QVBoxLayout
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QKeySequence

from danaurium import __version__, __app_name__
from danaurium.gui.tabs.editor_tab import EditorTab
from danaurium.gui.tabs.connections_tab import ConnectionsTab
from danaurium.gui.tabs.catalog_tab import CatalogTab
from danaurium.gui.tabs.lab_tab import LabTab
from danaurium.gui.tabs.budget_tab import BudgetTab
from danaurium.gui.tabs.prompts_tab import PromptsTab
from danaurium.gui.dialogs.backup_dialog import BackupRestoreDialog
from danaurium.security.keyring_manager import credentials
from danaurium.persistence.repository import repo


class MainWindow(QMainWindow):
    """Janela central integrando todas as abas de trabalho editorial."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{__app_name__} v{__version__}")
        self.resize(1280, 800)
        self.setMinimumSize(960, 640)

        # Abas principais
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.tab_editor = EditorTab(self)
        self.tab_connections = ConnectionsTab(self)
        self.tab_catalog = CatalogTab(self)
        self.tab_lab = LabTab(self)
        self.tab_budget = BudgetTab(self)
        self.tab_prompts = PromptsTab(self)

        self.tabs.addTab(self.tab_editor, "✍ Bancada de Redação")
        self.tabs.addTab(self.tab_catalog, "📚 Catálogo de Modelos")
        self.tabs.addTab(self.tab_connections, "🔌 Central de Conexões")
        self.tabs.addTab(self.tab_lab, "🔬 Laboratório de Comparação")
        self.tabs.addTab(self.tab_budget, "💰 Consumo e Orçamento")
        self.tabs.addTab(self.tab_prompts, "📑 Instruções Editoriais")

        self.tabs.currentChanged.connect(self._on_tab_changed)

        self._setup_menu()
        self._setup_status_bar()

    def _setup_menu(self):
        menubar = self.menuBar()

        # Menu Arquivo
        menu_file = menubar.addMenu("&Arquivo")

        act_new = QAction("&Novo Projeto", self)
        act_new.setShortcut(QKeySequence("Ctrl+N"))
        act_new.triggered.connect(self._new_project)
        menu_file.addAction(act_new)

        act_save = QAction("&Salvar Rascunho", self)
        act_save.setShortcut(QKeySequence("Ctrl+S"))
        act_save.triggered.connect(self.tab_editor._auto_save)
        menu_file.addAction(act_save)

        act_import = QAction("&Importar Matéria (TXT/DOCX/PDF)...", self)
        act_import.triggered.connect(self.tab_editor._import_file)
        menu_file.addAction(act_import)

        act_export_zip = QAction("&Exportar Pacote ZIP...", self)
        act_export_zip.setShortcut(QKeySequence("Ctrl+E"))
        act_export_zip.triggered.connect(self.tab_editor._export_project_zip)
        menu_file.addAction(act_export_zip)

        menu_file.addSeparator()

        act_backup = QAction("&Backup e Restauração da Base...", self)
        act_backup.triggered.connect(self._open_backup_dialog)
        menu_file.addAction(act_backup)

        menu_file.addSeparator()

        act_exit = QAction("&Sair", self)
        act_exit.setShortcut(QKeySequence("Ctrl+Q"))
        act_exit.triggered.connect(self.close)
        menu_file.addAction(act_exit)

        # Menu Ferramentas
        menu_tools = menubar.addMenu("&Ferramentas")

        act_extract = QAction("Extrair &Fatos da Matéria", self)
        act_extract.triggered.connect(self.tab_editor._extract_facts)
        menu_tools.addAction(act_extract)

        act_sync_all = QAction("&Atualizar Catálogos de IA", self)
        act_sync_all.triggered.connect(self._sync_all_catalogs)
        menu_tools.addAction(act_sync_all)

        # Menu Ajuda
        menu_help = menubar.addMenu("&Ajuda")

        act_diag = QAction("&Diagnóstico do Sistema e Conexão", self)
        act_diag.triggered.connect(self._show_system_diagnostics)
        menu_help.addAction(act_diag)

        act_about = QAction("&Sobre o Danaurium Redação Studio", self)
        act_about.triggered.connect(self._show_about)
        menu_help.addAction(act_about)

    def _setup_status_bar(self):
        status = self.statusBar()

        self.lbl_status_msg = QLabel("Pronto.")
        status.addWidget(self.lbl_status_msg, 1)

        # Indicador de segurança do cofre
        storage_mode = credentials.get_storage_mode_name()
        self.lbl_security = QLabel(f"🔐 Segurança: {storage_mode}")
        self.lbl_security.setStyleSheet("color: #495057; font-size: 11px; padding-right: 12px;")
        status.addPermanentWidget(self.lbl_security)

        self.lbl_save_status = QLabel("Auto-salvamento: Ativo")
        self.lbl_save_status.setStyleSheet("color: #2B8A3E; font-size: 11px; padding-right: 12px;")
        status.addPermanentWidget(self.lbl_save_status)

        lbl_ver = QLabel(f"v{__version__}")
        lbl_ver.setStyleSheet("color: #868E96; font-size: 11px;")
        status.addPermanentWidget(lbl_ver)

    def _on_tab_changed(self, index: int):
        # Atualizar dados contextuais ao alternar para a aba
        if index == 0:  # Bancada de redação
            self.tab_editor.refresh_models()
        elif index == 1:  # Catálogo
            self.tab_catalog.refresh_catalog()
        elif index == 3:  # Laboratório
            self.tab_lab.refresh_models()
        elif index == 4:  # Orçamento
            self.tab_budget.refresh_data()
        elif index == 5:  # Prompts
            self.tab_prompts.refresh_prompts()

    def _new_project(self):
        confirm = QMessageBox.question(
            self,
            "Novo Projeto",
            "Deseja iniciar uma nova matéria? O rascunho atual será salvo no banco histórico.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm == QMessageBox.Yes:
            self.tab_editor._auto_save()
            new_id = repo.save_project({"title": "Nova Matéria Jornalística", "raw_text": ""})
            self.tab_editor.current_project_id = new_id
            self.tab_editor.title_input.setText("Nova Matéria Jornalística")
            self.tab_editor.source_editor.setPlainText("")
            self.tab_editor.facts_table.setRowCount(0)
            self.tab_editor.results_tabs.clear()
            self.tabs.setCurrentIndex(0)

    def _open_backup_dialog(self):
        dlg = BackupRestoreDialog(self)
        dlg.exec()

    def _sync_all_catalogs(self):
        self.tabs.setCurrentIndex(2)  # Ir para conexões
        self.lbl_status_msg.setText("Para atualizar, selecione a conexão desejada e clique em 'Atualizar Catálogo'.")

    def _show_system_diagnostics(self):
        is_sec = credentials.is_secure_storage_active()
        mode_str = credentials.get_storage_mode_name()
        conns = repo.get_all_connections()
        models = repo.get_models()

        diag_text = (
            f"<b>{__app_name__} — Diagnóstico do Sistema</b><br><br>"
            f"<b>Versão:</b> {__version__}<br>"
            f"<b>Python:</b> {sys.version.split()[0]} ({sys.platform})<br>"
            f"<b>Cofre de Credenciais:</b> {mode_str}<br>"
            f"<b>Persistência Segura:</b> {'Ativa (Cofre do SO)' if is_sec else 'Sessão em Memória'}<br>"
            f"<b>Conexões Cadastradas:</b> {len(conns)}<br>"
            f"<b>Modelos no Catálogo Local:</b> {len(models)}<br>"
        )
        QMessageBox.information(self, "Diagnóstico do Sistema", diag_text)

    def _show_about(self):
        about_text = (
            f"<b>{__app_name__}</b> — Versão {__version__}<br><br>"
            "Desenvolvido sob medida para jornalistas, assessores de imprensa e comunicadores institucionais.<br><br>"
            "Permite transformar pautas e matérias-base em até 14 produtos editoriais com alta fidelidade factual, "
            "controle rigoroso de custos e suporte aos ecossistemas OpenAI, Anthropic e OpenRouter.<br><br>"
            "<i>Interface 100% em Português do Brasil. Dados e projetos armazenados estritamente no seu computador.</i>"
        )
        QMessageBox.about(self, "Sobre o Danaurium Redação Studio", about_text)

    def closeEvent(self, event):
        # Auto-salvar rascunho antes de encerrar
        try:
            self.tab_editor._auto_save()
        except Exception:
            pass
        event.accept()
