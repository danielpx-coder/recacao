"""Laboratório de comparação lado a lado entre múltiplos modelos de IA."""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTextEdit, QGroupBox, QSplitter, QTextBrowser,
    QSpinBox, QCheckBox, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt
from danaurium.persistence.repository import repo
from danaurium.catalog.pricing import calculate_cost_usd
from danaurium.editorial.fidelity import verify_editorial_fidelity
from danaurium.gui.workers import CompareLabWorker


class ModelCardWidget(QGroupBox):
    """Card individual que exibe o resultado e métricas de um modelo no laboratório."""

    def __init__(self, title: str, parent=None):
        super().__init__(title, parent)
        layout = QVBoxLayout(self)

        self.combo_model = QComboBox()
        layout.addWidget(QLabel("Modelo:"))
        layout.addWidget(self.combo_model)

        self.text_view = QTextBrowser()
        layout.addWidget(self.text_view, 1)

        # Métricas
        self.metrics_label = QLabel("Aguardando execução...")
        self.metrics_label.setStyleSheet("font-size: 11px; color: #495057;")
        layout.addWidget(self.metrics_label)

        # Avaliação manual do jornalista (1 a 5 estrelas)
        star_layout = QHBoxLayout()
        star_layout.addWidget(QLabel("Avaliação do Editor:"))
        self.star_spin = QSpinBox()
        self.star_spin.setRange(1, 5)
        self.star_spin.setValue(5)
        self.star_spin.setSuffix(" estrelas")
        star_layout.addWidget(self.star_spin)
        star_layout.addStretch()
        layout.addLayout(star_layout)

    def set_content(self, text: str, latency_ms: int, usage, cost_usd: Optional[Decimal], fidelity_warnings: list):
        self.text_view.setPlainText(text)
        cost_str = f"${cost_usd:.6f}" if cost_usd is not None else "Desconhecido"
        char_count = len(text)
        words_count = len(text.split())

        warnings_text = f" | <span style='color: #F08C00;'>Alertas: {len(fidelity_warnings)}</span>" if fidelity_warnings else " | Alertas: 0"

        metrics_html = f"""
        <b>Tempo:</b> {latency_ms} ms | <b>Tokens:</b> {usage.total_tokens} (In: {usage.input_tokens}, Out: {usage.output_tokens})<br>
        <b>Custo Estimado:</b> {cost_str} | <b>Tamanho:</b> {char_count} chars ({words_count} palavras){warnings_text}
        """
        self.metrics_label.setText(metrics_html)


class LabTab(QWidget):
    """Laboratório de comparação lado a lado de modelos jornalísticos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_worker = None

        layout = QVBoxLayout(self)

        # Configuração de entrada da tarefa
        top_grp = QGroupBox("Definição da Tarefa de Teste")
        t_lay = QVBoxLayout(top_grp)

        self.prompt_edit = QTextEdit()
        self.prompt_edit.setPlaceholderText("Insira o texto-fonte ou a pauta que deseja submeter simultaneamente aos modelos...")
        self.prompt_edit.setMaximumHeight(100)
        t_lay.addWidget(self.prompt_edit)

        # Controles de execução
        ctrl_bar = QHBoxLayout()
        self.show_pre_cost_check = QCheckBox("Exibir estimativa prévia do custo combinado (Desligado por padrão)")
        self.show_pre_cost_check.setChecked(False)
        ctrl_bar.addWidget(self.show_pre_cost_check)
        ctrl_bar.addStretch()

        self.btn_run = QPushButton("Executar Comparação")
        self.btn_run.setObjectName("primaryButton")
        self.btn_run.clicked.connect(self._run_comparison)
        ctrl_bar.addWidget(self.btn_run)

        self.btn_cancel = QPushButton("Cancelar")
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.clicked.connect(self._cancel_comparison)
        ctrl_bar.addWidget(self.btn_cancel)

        t_lay.addLayout(ctrl_bar)
        layout.addWidget(top_grp)

        # Área de cards de comparação lado a lado
        self.splitter = QSplitter(Qt.Horizontal)
        self.card1 = ModelCardWidget("Modelo 1")
        self.card2 = ModelCardWidget("Modelo 2")
        self.card3 = ModelCardWidget("Modelo 3")

        self.splitter.addWidget(self.card1)
        self.splitter.addWidget(self.card2)
        self.splitter.addWidget(self.card3)
        layout.addWidget(self.splitter, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.refresh_models()

    def refresh_models(self):
        models = repo.get_models(only_active=True)
        conns_map = {c["id"]: c["name"] for c in repo.get_all_connections()}

        for card in [self.card1, self.card2, self.card3]:
            card.combo_model.clear()
            for m in models:
                conn_name = conns_map.get(m["connection_id"], m["connection_id"])
                free_tag = "[GRÁTIS]" if m.get("is_free") else ""
                label = f"{m['display_name']} ({conn_name}) {free_tag}"
                card.combo_model.addItem(label, m)

        # Selecionar padrões distintos se existirem
        if len(models) >= 2:
            self.card2.combo_model.setCurrentIndex(1)
        if len(models) >= 3:
            self.card3.combo_model.setCurrentIndex(2)

    def _run_comparison(self):
        text = self.prompt_edit.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Aviso", "Informe um texto ou instrução para a comparação.")
            return

        m1 = self.card1.combo_model.currentData()
        m2 = self.card2.combo_model.currentData()
        m3 = self.card3.combo_model.currentData()

        selected_models = [m for m in [m1, m2, m3] if m]
        if len(selected_models) < 2:
            QMessageBox.warning(self, "Aviso", "Selecione ao menos 2 modelos para a comparação.")
            return

        # Estimativa prévia combinada se ativada
        if self.show_pre_cost_check.isChecked():
            est_tokens = max(1, int(len(text) / 3.8)) + 1500
            total_est_usd = Decimal("0.000000")
            for sm in selected_models:
                cost_dec, _ = calculate_cost_usd(
                    input_tokens=est_tokens,
                    output_tokens=1500,
                    pricing_prompt=sm.get("pricing_prompt"),
                    pricing_completion=sm.get("pricing_completion"),
                    pricing_unit=sm.get("pricing_unit", "per_1m_tokens"),
                )
                if cost_dec and not sm.get("is_free"):
                    total_est_usd += cost_dec

            confirm = QMessageBox.question(
                self,
                "Confirmar Custo Combinado Pré-Execução",
                f"A estimativa de custo total combinada para executar os {len(selected_models)} modelos é de aproximadamente "
                f"${total_est_usd:.6f} USD.\n\nDeseja prosseguir com a chamada simultânea?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if confirm != QMessageBox.Yes:
                return

        # Montar configurações para o trabalhador
        models_configs = []
        for m in selected_models:
            conn = repo.get_connection(m["connection_id"])
            if conn:
                models_configs.append({"connection_data": conn, "model_data": m})

        self.btn_run.setEnabled(False)
        self.btn_cancel.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, 0)  # Indeterminado

        system_prompt = "Você é um jornalista profissional redigindo com concisão, clareza e estrita fidelidade aos fatos."
        self.active_worker = CompareLabWorker(
            task_prompt=text,
            system_prompt=system_prompt,
            models_configs=models_configs,
            parent=self,
        )

        self.active_worker.model_finished.connect(self._on_model_result)
        self.active_worker.all_finished.connect(self._on_all_finished)
        self.active_worker.error_occurred.connect(self._on_error)
        self.active_worker.start()

    def _on_model_result(self, model_key: str, data: dict):
        # Localizar qual card corresponde a este modelo
        for card in [self.card1, self.card2, self.card3]:
            m = card.combo_model.currentData()
            if m and f"{m['connection_id']}::{m['model_id']}" == model_key:
                fidelity_warnings = verify_editorial_fidelity(
                    source_text=self.prompt_edit.toPlainText(),
                    generated_text=data["text"],
                )
                card.set_content(
                    text=data["text"],
                    latency_ms=data["latency_ms"],
                    usage=data["usage"],
                    cost_usd=data["cost_usd"],
                    fidelity_warnings=fidelity_warnings,
                )
                break

    def _on_error(self, model_key: str, err_msg: str):
        for card in [self.card1, self.card2, self.card3]:
            m = card.combo_model.currentData()
            if m and f"{m['connection_id']}::{m['model_id']}" == model_key:
                card.text_view.setPlainText(f"ERRO NA GERAÇÃO: {err_msg}")
                card.metrics_label.setText(f"<span style='color: #C92A2A;'>Falha: {err_msg}</span>")
                break

    def _on_all_finished(self):
        self.btn_run.setEnabled(True)
        self.btn_cancel.setEnabled(False)
        self.progress_bar.setVisible(False)

    def _cancel_comparison(self):
        if self.active_worker:
            self.active_worker.cancel()
            self._on_all_finished()
