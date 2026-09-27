"""Diálogo de backup e restauração do banco de dados SQLite."""

from pathlib import Path
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QMessageBox, QGroupBox
)
from danaurium.persistence.backup import create_backup, restore_backup
from danaurium.config import paths


class BackupRestoreDialog(QDialog):
    """Interface para criação e restauração consistente de backups locais."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Backup e Restauração da Base de Dados")
        self.resize(520, 320)

        layout = QVBoxLayout(self)

        # Seção Backup
        grp_backup = QGroupBox("Criar Cópia de Segurança (Backup)")
        b_lay = QVBoxLayout(grp_backup)
        b_lay.addWidget(QLabel("Gera uma cópia íntegra e segura de todos os projetos, versões e configurações.<br>"
                               "<b>Nota:</b> Nenhuma chave de API ou segredo é gravado no backup."))
        
        self.btn_create = QPushButton("Criar Backup Agora...")
        self.btn_create.setObjectName("primaryButton")
        self.btn_create.clicked.connect(self._create_backup)
        b_lay.addWidget(self.btn_create)
        layout.addWidget(grp_backup)

        # Seção Restauração
        grp_restore = QGroupBox("Restaurar Base de Dados")
        r_lay = QVBoxLayout(grp_restore)
        r_lay.addWidget(QLabel("Restaura um backup anterior. Uma cópia do banco atual será gerada automaticamente antes da substituição."))
        
        self.btn_restore = QPushButton("Selecionar Arquivo de Backup para Restaurar...")
        self.btn_restore.clicked.connect(self._restore_backup)
        r_lay.addWidget(self.btn_restore)
        layout.addWidget(grp_restore)

        # Botão fechar
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.btn_close = QPushButton("Fechar")
        self.btn_close.clicked.connect(self.accept)
        btn_layout.addWidget(self.btn_close)
        layout.addLayout(btn_layout)

    def _create_backup(self):
        dest_dir = paths.backups_dir
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Arquivo de Backup",
            str(dest_dir / "danaurium_backup.db"),
            "Banco SQLite (*.db);;Todos os Arquivos (*.*)",
        )
        if file_path:
            try:
                out = create_backup(Path(file_path))
                QMessageBox.information(
                    self,
                    "Backup Concluído",
                    f"Backup criado com sucesso em:\n{out}",
                )
            except Exception as e:
                QMessageBox.critical(self, "Erro no Backup", f"Falha ao gerar backup: {e}")

    def _restore_backup(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Selecionar Arquivo de Backup",
            str(paths.backups_dir),
            "Banco SQLite (*.db);;Todos os Arquivos (*.*)",
        )
        if file_path:
            confirm = QMessageBox.question(
                self,
                "Confirmar Restauração",
                "Tem certeza que deseja restaurar este backup? O banco atual será substituído após salvamento de segurança.",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm == QMessageBox.Yes:
                try:
                    restore_backup(Path(file_path))
                    QMessageBox.information(
                        self,
                        "Restauração Concluída",
                        "A base de dados foi restaurada com sucesso!",
                    )
                except Exception as e:
                    QMessageBox.critical(self, "Erro na Restauração", f"Falha ao restaurar backup: {e}")
