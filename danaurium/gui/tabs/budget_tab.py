"""Painel de consumo, faturamento, conversão BRL e gestão de limites de orçamento."""

from decimal import Decimal
from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QGroupBox, QLineEdit, QCheckBox, QMessageBox, QProgressBar
)
from PySide6.QtCore import Qt
from danaurium.persistence.repository import repo
from danaurium.budget.tracker import usage_tracker


class BudgetTab(QWidget):
    """Aba de monitoramento financeiro de chamadas de IA e controle de gastos."""

    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Filtro de período e escopo
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("<b>Período:</b>"))
        self.period_combo = QComboBox()
        self.period_combo.addItem("Hoje", "today")
        self.period_combo.addItem("Esta Semana", "this_week")
        self.period_combo.addItem("Este Mês", "this_month")
        self.period_combo.addItem("Todo o Histórico", "all")
        self.period_combo.setCurrentIndex(2)  # Este Mês como padrão
        self.period_combo.currentIndexChanged.connect(self.refresh_data)
        filter_bar.addWidget(self.period_combo)

        filter_bar.addStretch()

        self.btn_refresh = QPushButton("Atualizar Dados")
        self.btn_refresh.clicked.connect(self.refresh_data)
        filter_bar.addWidget(self.btn_refresh)
        layout.addLayout(filter_bar)

        # Cards de métricas principais
        cards_layout = QHBoxLayout()

        self.card_spend_usd = QGroupBox("Gasto Calculado (USD)")
        c1_lay = QVBoxLayout(self.card_spend_usd)
        self.lbl_spend_usd = QLabel("$0.000000 USD")
        self.lbl_spend_usd.setStyleSheet("font-size: 18px; font-weight: bold; color: #0B7285;")
        c1_lay.addWidget(self.lbl_spend_usd)
        cards_layout.addWidget(self.card_spend_usd)

        self.card_spend_brl = QGroupBox("Conversão em Reais (BRL)")
        c2_lay = QVBoxLayout(self.card_spend_brl)
        self.lbl_spend_brl = QLabel("R$ 0.00")
        self.lbl_spend_brl.setStyleSheet("font-size: 18px; font-weight: bold; color: #2B8A3E;")
        self.lbl_brl_info = QLabel("Cotação: R$ 5.50 em 2026-09-27")
        self.lbl_brl_info.setStyleSheet("font-size: 11px; color: #868E96;")
        c2_lay.addWidget(self.lbl_spend_brl)
        c2_lay.addWidget(self.lbl_brl_info)
        cards_layout.addWidget(self.card_spend_brl)

        self.card_tokens = QGroupBox("Tokens Consumidos")
        c3_lay = QVBoxLayout(self.card_tokens)
        self.lbl_tokens = QLabel("0 tokens")
        self.lbl_tokens.setStyleSheet("font-size: 18px; font-weight: bold; color: #343A40;")
        self.lbl_tokens_detail = QLabel("In: 0 | Out: 0 | Cache: 0 | Raciocínio: 0")
        self.lbl_tokens_detail.setStyleSheet("font-size: 11px; color: #495057;")
        c3_lay.addWidget(self.lbl_tokens)
        c3_lay.addWidget(self.lbl_tokens_detail)
        cards_layout.addWidget(self.card_tokens)

        self.card_reqs = QGroupBox("Requisições / Latência")
        c4_lay = QVBoxLayout(self.card_reqs)
        self.lbl_reqs = QLabel("0 chamadas")
        self.lbl_reqs.setStyleSheet("font-size: 18px; font-weight: bold; color: #343A40;")
        self.lbl_latency = QLabel("Latência Média: 0 ms")
        self.lbl_latency.setStyleSheet("font-size: 11px; color: #495057;")
        c4_lay.addWidget(self.lbl_reqs)
        c4_lay.addWidget(self.lbl_latency)
        cards_layout.addWidget(self.card_reqs)

        layout.addLayout(cards_layout)

        # Configurações de Tetos e Limites
        limit_grp = QGroupBox("Configuração de Tetos Orçamentários e Modos de Segurança")
        l_form = QHBoxLayout(limit_grp)

        l_form.addWidget(QLabel("Teto Diário (USD):"))
        self.daily_limit_edit = QLineEdit()
        self.daily_limit_edit.setFixedWidth(80)
        l_form.addWidget(self.daily_limit_edit)

        l_form.addWidget(QLabel("Teto Mensal (USD):"))
        self.monthly_limit_edit = QLineEdit()
        self.monthly_limit_edit.setFixedWidth(80)
        l_form.addWidget(self.monthly_limit_edit)

        l_form.addWidget(QLabel("Cotação USD/BRL:"))
        self.brl_rate_edit = QLineEdit()
        self.brl_rate_edit.setFixedWidth(70)
        l_form.addWidget(self.brl_rate_edit)

        self.strict_budget_check = QCheckBox("Modo Orçamento Estrito (Bloqueia preço desconhecido)")
        l_form.addWidget(self.strict_budget_check)

        self.btn_save_limits = QPushButton("Salvar Tetos")
        self.btn_save_limits.clicked.connect(self._save_budget_settings)
        l_form.addWidget(self.btn_save_limits)

        layout.addWidget(limit_grp)

        # Tabela com histórico detalhado
        layout.addWidget(QLabel("<b>Detalhamento de Consumo por Chamada</b>"))
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Data / Hora", "Conexão", "Modelo", "Produto / Tarefa",
            "Tokens Entrada", "Tokens Saída", "Estimativa Prévia", "Custo Calculado", "Status"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        layout.addWidget(self.table, 1)

        # Aviso Legal e Esclarecimento
        disclaimer = QLabel(
            "<i>Nota informativa: O controle local cobre as requisições realizadas através deste aplicativo "
            "e baseia-se nas tabelas de preços conhecidas e no consumo informado pelas APIs. "
            "Este controle não substitui a fatura financeira oficial emitida pelos provedores.</i>"
        )
        disclaimer.setStyleSheet("color: #868E96; font-size: 11px;")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)

        self._load_budget_settings()
        self.refresh_data()

    def _load_budget_settings(self):
        settings = repo.get_budget_settings()
        self.daily_limit_edit.setText(str(settings.get("daily_limit_usd", "10.00")))
        self.monthly_limit_edit.setText(str(settings.get("monthly_limit_usd", "100.00")))
        self.brl_rate_edit.setText(str(settings.get("usd_to_brl_rate", "5.50")))
        self.strict_budget_check.setChecked(bool(settings.get("strict_budget_mode", False)))

    def _save_budget_settings(self):
        settings = repo.get_budget_settings()
        settings["daily_limit_usd"] = self.daily_limit_edit.text().strip()
        settings["monthly_limit_usd"] = self.monthly_limit_edit.text().strip()
        settings["usd_to_brl_rate"] = self.brl_rate_edit.text().strip()
        settings["strict_budget_mode"] = self.strict_budget_check.isChecked()

        repo.update_budget_settings(settings)
        QMessageBox.information(self, "Sucesso", "Configurações de limites e cotação atualizadas.")
        self.refresh_data()

    def refresh_data(self):
        period = self.period_combo.currentData()
        summary = usage_tracker.get_summary(period=period)

        costs = summary["costs"]
        tokens = summary["tokens"]

        calc_usd = costs["calculated_by_app_usd"]
        calc_brl = costs["calculated_by_app_brl"]

        self.lbl_spend_usd.setText(f"${calc_usd:.6f} USD")
        self.lbl_spend_brl.setText(f"R$ {calc_brl:.4f}" if calc_brl is not None else "R$ 0,00")
        self.lbl_brl_info.setText(costs["brl_conversion_info"])

        self.lbl_tokens.setText(f"{tokens['total']:,} tokens".replace(",", "."))
        self.lbl_tokens_detail.setText(
            f"In: {tokens['input']:,} | Out: {tokens['output']:,} | Cache: {tokens['cache']:,} | Raciocínio: {tokens['reasoning']:,}".replace(",", ".")
        )

        self.lbl_reqs.setText(f"{summary['total_requests']} chamadas")
        self.lbl_latency.setText(f"Latência Média: {summary['average_latency_ms']} ms")

        # Preencher tabela
        logs = summary["raw_logs"]
        self.table.setRowCount(len(logs))
        for r_idx, l in enumerate(logs):
            dt_str = (l.get("created_at") or "")[:19].replace("T", " ")
            self.table.setItem(r_idx, 0, QTableWidgetItem(dt_str))
            self.table.setItem(r_idx, 1, QTableWidgetItem(l.get("connection_id") or "-"))
            self.table.setItem(r_idx, 2, QTableWidgetItem(l.get("model_id") or "-"))
            self.table.setItem(r_idx, 3, QTableWidgetItem(l.get("product_id") or l.get("task_type") or "-"))
            self.table.setItem(r_idx, 4, QTableWidgetItem(str(l.get("tokens_input", 0))))
            self.table.setItem(r_idx, 5, QTableWidgetItem(str(l.get("tokens_output", 0))))
            self.table.setItem(r_idx, 6, QTableWidgetItem(f"${l.get('pre_flight_estimate', '0')}"))
            self.table.setItem(r_idx, 7, QTableWidgetItem(f"${l.get('cost_calculated', '0')}"))
            self.table.setItem(r_idx, 8, QTableWidgetItem(l.get("status", "ok")))
