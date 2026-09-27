"""Aba principal da bancada de redação editorial do Danaurium Redação Studio."""

import os
from pathlib import Path
from decimal import Decimal
from typing import Any, Dict, List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QLineEdit, QComboBox, QCheckBox, QGroupBox,
    QTabWidget, QSplitter, QProgressBar, QMessageBox, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView, QMenu
)
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QClipboard, QAction

from danaurium.persistence.repository import repo
from danaurium.editorial.products import EDITORIAL_PRODUCTS, EditorialProductDefinition
from danaurium.editorial.fidelity import extract_facts_heuristic, verify_editorial_fidelity
from danaurium.editorial.radio import calculate_radio_duration
from danaurium.catalog.pricing import estimate_pre_flight_cost, calculate_cost_usd
from danaurium.catalog.manager import catalog_manager
from danaurium.io.importers import import_file, ImportErrorWithDiagnostics
from danaurium.io.exporters import (
    export_txt, export_docx, export_markdown, export_wordpress_html, export_project_zip
)
from danaurium.gui.workers import GenerationWorker
from danaurium.gui.dialogs.rewrite_dialog import RewriteSelectionDialog
from danaurium.gui.dialogs.diff_dialog import VersionDiffDialog
from danaurium.config import paths


class ProductResultView(QWidget):
    """Visualizador e editor de um produto editorial gerado com controle de versões e métricas."""

    def __init__(self, product_id: str, project_id: str, on_rewrite_requested, parent=None):
        super().__init__(parent)
        self.product_id = product_id
        self.project_id = project_id
        self.on_rewrite_requested = on_rewrite_requested
        self.product_def = EDITORIAL_PRODUCTS.get(product_id)
        self.current_versions = []

        layout = QVBoxLayout(self)

        # Barra superior do produto
        top_bar = QHBoxLayout()
        top_bar.addWidget(QLabel(f"<b>{self.product_def.name if self.product_def else product_id}</b>"))

        top_bar.addWidget(QLabel("Versão:"))
        self.version_combo = QComboBox()
        self.version_combo.currentIndexChanged.connect(self._on_version_selected)
        top_bar.addWidget(self.version_combo)

        self.btn_diff = QPushButton("Comparar Versões")
        self.btn_diff.clicked.connect(self._open_diff)
        top_bar.addWidget(self.btn_diff)

        self.btn_rewrite = QPushButton("Reescrever Seleção...")
        self.btn_rewrite.clicked.connect(self._on_rewrite_click)
        top_bar.addWidget(self.btn_rewrite)

        self.btn_copy = QPushButton("Copiar")
        self.btn_copy.clicked.connect(self._copy_text)
        top_bar.addWidget(self.btn_copy)

        # Botão Exportar com menu
        self.btn_export = QPushButton("Exportar Produto ▾")
        self.export_menu = QMenu(self)
        act_txt = self.export_menu.addAction("Exportar como TXT")
        act_docx = self.export_menu.addAction("Exportar como Word (.docx)")
        act_md = self.export_menu.addAction("Exportar como Markdown (.md)")
        act_html = self.export_menu.addAction("Exportar como HTML (WordPress)")
        act_txt.triggered.connect(lambda: self._export_single("txt"))
        act_docx.triggered.connect(lambda: self._export_single("docx"))
        act_md.triggered.connect(lambda: self._export_single("md"))
        act_html.triggered.connect(lambda: self._export_single("html"))
        self.btn_export.setMenu(self.export_menu)
        top_bar.addWidget(self.btn_export)

        layout.addLayout(top_bar)

        # Editor de texto
        self.editor = QTextEdit()
        self.editor.textChanged.connect(self._update_counters)
        layout.addWidget(self.editor, 1)

        # Barra de status do produto (contadores e alertas)
        bottom_bar = QHBoxLayout()
        self.lbl_counts = QLabel("0 caracteres | 0 palavras")
        bottom_bar.addWidget(self.lbl_counts)

        self.lbl_limit_badge = QLabel("Limite: 1800")
        self.lbl_limit_badge.setObjectName("charCountBadge")
        bottom_bar.addWidget(self.lbl_limit_badge)

        self.lbl_radio_time = QLabel("")
        bottom_bar.addWidget(self.lbl_radio_time)

        bottom_bar.addStretch()
        self.lbl_metrics = QLabel("")
        bottom_bar.addWidget(self.lbl_metrics)

        layout.addLayout(bottom_bar)

        # Painel de alertas de fidelidade (invisível se não houver alertas)
        self.fidelity_box = QLabel()
        self.fidelity_box.setStyleSheet(
            "background-color: #FFF9DB; border: 1px solid #FFE066; "
            "padding: 6px; border-radius: 4px; color: #744210; font-size: 11px;"
        )
        self.fidelity_box.setWordWrap(True)
        self.fidelity_box.setVisible(False)
        layout.addWidget(self.fidelity_box)

        self.load_versions()

    def set_content(self, text: str):
        self.editor.setPlainText(text)
        self._update_counters()

    def append_chunk(self, chunk_text: str):
        self.editor.moveCursor(self.editor.textCursor().End)
        self.editor.insertPlainText(chunk_text)
        self._update_counters()

    def load_versions(self):
        if not self.project_id:
            return
        vers = repo.get_versions(self.project_id, self.product_id)
        self.current_versions = vers

        self.version_combo.blockSignals(True)
        self.version_combo.clear()
        for v in vers:
            label = f"v{v['version_number']} ({v.get('created_at', '')[11:19]})"
            self.version_combo.addItem(label, v)
        self.version_combo.blockSignals(False)

        if vers:
            latest = vers[0]
            self.set_content(latest["content"])
            self.show_version_metadata(latest)

    def show_version_metadata(self, ver: Dict[str, Any]):
        cost_str = ver.get("cost_calculated", "0.000000")
        lat = ver.get("latency_ms", 0)
        tok_out = ver.get("tokens_output", 0)
        self.lbl_metrics.setText(f"Modelo: {ver.get('model_used', '-')} | Latência: {lat} ms | Tokens: {tok_out} | Custo: ${cost_str}")

        warnings = ver.get("fidelity_warnings", [])
        if warnings:
            w_text = "<br>".join([f"• <b>{w['type']}:</b> {w['message']}" for w in warnings])
            self.fidelity_box.setText(f"<b>Alertas de Fidelidade Editorial:</b><br>{w_text}")
            self.fidelity_box.setVisible(True)
        else:
            self.fidelity_box.setVisible(False)

    def _on_version_selected(self, index: int):
        v = self.version_combo.currentData()
        if v:
            self.set_content(v["content"])
            self.show_version_metadata(v)

    def _update_counters(self):
        text = self.editor.toPlainText()
        chars = len(text)
        words = len(text.split())
        self.lbl_counts.setText(f"{chars:,} caracteres | {words:,} palavras".replace(",", "."))

        # Indicador de limite
        preset = self.product_def.default_char_limit if self.product_def else 1800
        if chars > preset:
            self.lbl_limit_badge.setStyleSheet("background-color: #FFE3E3; color: #C92A2A;")
            self.lbl_limit_badge.setText(f"Limite ({preset}): +{chars - preset} excedidos")
        elif chars >= int(preset * 0.9):
            self.lbl_limit_badge.setStyleSheet("background-color: #FFF3BF; color: #D9480F;")
            self.lbl_limit_badge.setText(f"Limite: {chars} / {preset} (Próximo)")
        else:
            self.lbl_limit_badge.setStyleSheet("background-color: #EBFBEE; color: #2B8A3E;")
            self.lbl_limit_badge.setText(f"Limite: {chars} / {preset} (OK)")

        # Cálculo de tempo de rádio para spots e roteiros
        if self.product_id in ("spot_radio", "roteiro_dois_locutores"):
            radio_data = calculate_radio_duration(text)
            self.lbl_radio_time.setText(f"⏱ <b>Duração Estimada: {radio_data['formatted_time']}</b> (135 ppm)")
        else:
            self.lbl_radio_time.setText("")

    def _copy_text(self):
        text = self.editor.toPlainText()
        if text:
            from PySide6.QtWidgets import QApplication
            QApplication.clipboard().setText(text)
            self.btn_copy.setText("Copiado!")
            QTimer.singleShot(2000, lambda: self.btn_copy.setText("Copiar"))

    def _on_rewrite_click(self):
        cursor = self.editor.textCursor()
        selected = cursor.selectedText()
        if not selected.strip():
            # Se nada selecionado, seleciona todo o texto
            selected = self.editor.toPlainText()

        if not selected.strip():
            QMessageBox.information(self, "Aviso", "O texto está vazio.")
            return

        dlg = RewriteSelectionDialog(selected_text=selected, parent=self)
        if dlg.exec() == QDialog.Accepted:
            instruction = dlg.get_instruction()
            self.on_rewrite_requested(self.product_id, selected, instruction)

    def _open_diff(self):
        if len(self.current_versions) < 2:
            QMessageBox.information(self, "Aviso", "São necessárias ao menos duas versões salvas para comparar.")
            return
        dlg = VersionDiffDialog(self.current_versions, parent=self)
        dlg.exec()

    def _export_single(self, fmt: str):
        text = self.editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Aviso", "Não há texto para exportar.")
            return

        title = f"{self.product_id}"
        ext_map = {"txt": "txt", "docx": "docx", "md": "md", "html": "html"}
        out_name = f"{title}.{ext_map[fmt]}"

        target_file, _ = QFileDialog.getSaveFileName(
            self,
            f"Exportar {self.product_id.upper()}",
            str(paths.exports_dir / out_name),
            f"Arquivo (*.{ext_map[fmt]})",
        )
        if target_file:
            p = Path(target_file)
            if fmt == "txt":
                export_txt(p, text)
            elif fmt == "docx":
                export_docx(p, title, text)
            elif fmt == "md":
                export_markdown(p, title, text)
            elif fmt == "html":
                export_wordpress_html(p, title, text)

            QMessageBox.information(self, "Exportação Concluída", f"Arquivo salvo com sucesso em:\n{p}")


class EditorTab(QWidget):
    """Bancada de Redação: entrada de matéria, extração de fatos, produtos e geração."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.active_generation_worker = None
        self.current_project_id = None
        self.extracted_facts_cache = []

        layout = QVBoxLayout(self)

        # Divisor principal: Esquerda (Texto-fonte & Fatos) e Direita (Configuração & Resultados)
        self.main_splitter = QSplitter(Qt.Horizontal)

        # ==========================================
        # PAINEL ESQUERDO: FONTE E FATOS EXTRAÍDOS
        # ==========================================
        left_widget = QWidget()
        left_lay = QVBoxLayout(left_widget)
        left_lay.setContentsMargins(0, 0, 0, 0)

        # Cabeçalho do projeto
        p_hdr = QHBoxLayout()
        p_hdr.addWidget(QLabel("<b>Título do Projeto:</b>"))
        self.title_input = QLineEdit("Nova Matéria Jornalística")
        self.title_input.textChanged.connect(self._mark_dirty)
        p_hdr.addWidget(self.title_input)

        self.btn_import_file = QPushButton("Importar Arquivo...")
        self.btn_import_file.clicked.connect(self._import_file)
        p_hdr.addWidget(self.btn_import_file)
        left_lay.addLayout(p_hdr)

        # Editor do texto-fonte
        left_lay.addWidget(QLabel("<b>Texto-Base / Matéria-Fonte:</b>"))
        self.source_editor = QTextEdit()
        self.source_editor.setPlaceholderText("Cole o texto-base da matéria, release ou documento aqui...")
        self.source_editor.textChanged.connect(self._on_source_text_changed)
        left_lay.addWidget(self.source_editor, 1)

        self.lbl_source_counts = QLabel("0 caracteres | 0 palavras")
        self.lbl_source_counts.setStyleSheet("color: #868E96; font-size: 11px;")
        left_lay.addWidget(self.lbl_source_counts)

        # Painel de Fatos Extraídos
        facts_group = QGroupBox("Painel de Fatos Extraídos da Fonte (Ground Truth)")
        f_lay = QVBoxLayout(facts_group)

        f_actions = QHBoxLayout()
        self.btn_extract_facts = QPushButton("Extrair Fatos da Fonte")
        self.btn_extract_facts.clicked.connect(self._extract_facts)
        f_actions.addWidget(self.btn_extract_facts)
        f_actions.addStretch()
        f_lay.addLayout(f_actions)

        self.facts_table = QTableWidget()
        self.facts_table.setColumnCount(3)
        self.facts_table.setHorizontalHeaderLabels(["Fixar", "Referência", "Fato / Citação / Número"])
        self.facts_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.facts_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.facts_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.facts_table.setMaximumHeight(160)
        f_lay.addWidget(self.facts_table)

        left_lay.addWidget(facts_group)
        self.main_splitter.addWidget(left_widget)

        # ==========================================
        # PAINEL DIREITO: PRODUTOS, CONFIGURAÇÃO E RESULTADOS
        # ==========================================
        right_widget = QWidget()
        right_lay = QVBoxLayout(right_widget)
        right_lay.setContentsMargins(0, 0, 0, 0)

        # Configurações de Modelo e Perfil
        config_box = QGroupBox("Configuração de IA e Diretrizes Editoriais")
        cfg_lay = QVBoxLayout(config_box)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("Perfil Editorial:"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(["Econômico", "Somente Gratuitos", "Equilibrado", "Qualidade Prioritária", "Personalizado"])
        self.profile_combo.currentIndexChanged.connect(self._on_profile_changed)
        r1.addWidget(self.profile_combo)

        r1.addWidget(QLabel("Modelo:"))
        self.model_combo = QComboBox()
        self.model_combo.currentIndexChanged.connect(self._update_pre_flight_estimate)
        r1.addWidget(self.model_combo, 1)
        cfg_lay.addLayout(r1)

        # Parâmetros editoriais
        r2 = QHBoxLayout()
        r2.addWidget(QLabel("Tom:"))
        self.tone_combo = QComboBox()
        self.tone_combo.addItems([
            "Equilibrado e Jornalístico",
            "Formal e Institucional",
            "Acessível e Didático",
            "Analítico e Aprofundado",
            "Coloquial e Dinâmico",
        ])
        r2.addWidget(self.tone_combo)

        r2.addWidget(QLabel("Público:"))
        self.audience_edit = QLineEdit("Público Geral")
        r2.addWidget(self.audience_edit)

        r2.addWidget(QLabel("Pessoa Verbal:"))
        self.person_combo = QComboBox()
        self.person_combo.addItems(["3ª pessoa", "1ª pessoa do plural (Nós institucional)", "1ª pessoa do singular"])
        r2.addWidget(self.person_combo)

        r2.addWidget(QLabel("Limite:"))
        self.limit_combo = QComboBox()
        self.limit_combo.addItems(["1.400 chars", "1.800 chars", "2.000 chars", "2.500 chars"])
        self.limit_combo.setCurrentIndex(1)
        r2.addWidget(self.limit_combo)
        cfg_lay.addLayout(r2)

        # Termos obrigatórios e proibidos
        r3 = QHBoxLayout()
        r3.addWidget(QLabel("Termos Obrigatórios:"))
        self.mandatory_edit = QLineEdit()
        self.mandatory_edit.setPlaceholderText("Separados por vírgula (ex: MEC, 2026, Inep)")
        r3.addWidget(self.mandatory_edit)

        r3.addWidget(QLabel("Termos Proibidos:"))
        self.forbidden_edit = QLineEdit()
        self.forbidden_edit.setPlaceholderText("Separados por vírgula")
        r3.addWidget(self.forbidden_edit)
        cfg_lay.addLayout(r3)

        right_lay.addWidget(config_box)

        # Seleção de Produtos Editoriais (14 produtos)
        prod_box = QGroupBox("Produtos Editoriais a Gerar")
        p_lay = QVBoxLayout(prod_box)

        p_sel_bar = QHBoxLayout()
        self.btn_sel_all = QPushButton("Selecionar Todos")
        self.btn_sel_all.clicked.connect(self._select_all_products)
        self.btn_clear_sel = QPushButton("Limpar Seleção")
        self.btn_clear_sel.clicked.connect(self._clear_product_selection)
        p_sel_bar.addWidget(self.btn_sel_all)
        p_sel_bar.addWidget(self.btn_clear_sel)
        p_sel_bar.addStretch()
        p_lay.addLayout(p_sel_bar)

        # Grid de Checkboxes de produtos
        self.product_checks: Dict[str, QCheckBox] = {}
        chk_layout1 = QHBoxLayout()
        chk_layout2 = QHBoxLayout()

        products_list = list(EDITORIAL_PRODUCTS.values())
        for idx, prod in enumerate(products_list):
            chk = QCheckBox(prod.name)
            chk.setChecked(idx < 3)  # Seleciona os 3 primeiros por padrão
            chk.toggled.connect(self._update_pre_flight_estimate)
            self.product_checks[prod.id] = chk
            if idx < 7:
                chk_layout1.addWidget(chk)
            else:
                chk_layout2.addWidget(chk)

        p_lay.addLayout(chk_layout1)
        p_lay.addLayout(chk_layout2)
        right_lay.addWidget(prod_box)

        # Barra de Ação de Geração e Estimativa Prévia
        gen_bar = QHBoxLayout()
        self.lbl_pre_flight = QLabel("Previsão: 0 chamadas | Custo: $0.000000")
        self.lbl_pre_flight.setStyleSheet("font-weight: bold; color: #0B7285;")
        gen_bar.addWidget(self.lbl_pre_flight)

        gen_bar.addStretch()

        self.btn_cancel_gen = QPushButton("Cancelar")
        self.btn_cancel_gen.setObjectName("dangerButton")
        self.btn_cancel_gen.setEnabled(False)
        self.btn_cancel_gen.clicked.connect(self._cancel_generation)
        gen_bar.addWidget(self.btn_cancel_gen)

        self.btn_generate = QPushButton("Gerar Produtos Selecionados")
        self.btn_generate.setObjectName("primaryButton")
        self.btn_generate.clicked.connect(self._start_generation)
        gen_bar.addWidget(self.btn_generate)

        self.btn_export_all = QPushButton("Exportar Pacote ZIP...")
        self.btn_export_all.clicked.connect(self._export_project_zip)
        gen_bar.addWidget(self.btn_export_all)

        right_lay.addLayout(gen_bar)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        right_lay.addWidget(self.progress_bar)

        # Abas com os Resultados Gerados
        self.results_tabs = QTabWidget()
        right_lay.addWidget(self.results_tabs, 1)

        self.main_splitter.addWidget(right_widget)
        self.main_splitter.setStretchFactor(0, 4)
        self.main_splitter.setStretchFactor(1, 6)
        layout.addWidget(self.main_splitter)

        # Timer para auto-save de rascunho
        self.auto_save_timer = QTimer(self)
        self.auto_save_timer.timeout.connect(self._auto_save)
        self.auto_save_timer.start(30000)  # A cada 30 segundos

        self._init_new_project()
        self.refresh_models()
        self._update_pre_flight_estimate()

    def _init_new_project(self):
        """Inicializa um novo projeto vazio ou recupera o último em aberto."""
        # Verificar recuperação de fechamento inesperado
        last_draft = repo.get_app_state("active_draft")
        if last_draft:
            try:
                import json
                data = json.loads(last_draft)
                self.title_input.setText(data.get("title", "Projeto Recuperado"))
                self.source_editor.setPlainText(data.get("raw_text", ""))
                self.current_project_id = data.get("id")
                return
            except Exception:
                pass

        proj_id = repo.save_project({
            "title": self.title_input.text().strip(),
            "raw_text": "",
        })
        self.current_project_id = proj_id

    def _mark_dirty(self):
        pass

    def _auto_save(self):
        """Executa salvamento automático periódico e registra no app_state."""
        if not self.current_project_id:
            return

        limit_val = int(self.limit_combo.currentText().replace(".", "").split()[0])
        checked_prods = [p_id for p_id, chk in self.product_checks.items() if chk.isChecked()]

        data = {
            "id": self.current_project_id,
            "title": self.title_input.text().strip(),
            "raw_text": self.source_editor.toPlainText(),
            "extracted_facts": self._get_pinned_facts(),
            "selected_products": checked_prods,
            "tone": self.tone_combo.currentText(),
            "audience": self.audience_edit.text().strip(),
            "grammatical_person": self.person_combo.currentText(),
            "mandatory_words": self.mandatory_edit.text().strip(),
            "forbidden_expressions": self.forbidden_edit.text().strip(),
            "char_limit_preset": limit_val,
        }
        repo.save_project(data)

        # Salvar estado para recuperação de travamento
        import json
        repo.set_app_state("active_draft", json.dumps(data))

    def refresh_models(self):
        models = repo.get_models(only_active=True)
        conns_map = {c["id"]: c["name"] for c in repo.get_all_connections()}

        self.model_combo.blockSignals(True)
        self.model_combo.clear()
        for m in models:
            c_name = conns_map.get(m["connection_id"], m["connection_id"])
            p_in = m.get("pricing_prompt")
            p_label = "Grátis" if m.get("is_free") else (f"${p_in}/1M" if p_in is not None else "Preço desc.")
            label = f"{m['display_name']} ({c_name}) — [{p_label}]"
            self.model_combo.addItem(label, m)
        self.model_combo.blockSignals(False)

    def _on_profile_changed(self):
        profile = self.profile_combo.currentText()
        if profile == "Somente Gratuitos":
            # Selecionar o primeiro modelo gratuito disponível
            for idx in range(self.model_combo.count()):
                m = self.model_combo.itemData(idx)
                if m and m.get("is_free"):
                    self.model_combo.setCurrentIndex(idx)
                    break
        elif profile == "Econômico":
            for idx in range(self.model_combo.count()):
                m = self.model_combo.itemData(idx)
                if m and m.get("personal_category") == "Econômico":
                    self.model_combo.setCurrentIndex(idx)
                    break
        elif profile == "Equilibrado":
            for idx in range(self.model_combo.count()):
                m = self.model_combo.itemData(idx)
                if m and m.get("personal_category") == "Intermediário":
                    self.model_combo.setCurrentIndex(idx)
                    break

        self._update_pre_flight_estimate()

    def _on_source_text_changed(self):
        text = self.source_editor.toPlainText()
        self.lbl_source_counts.setText(f"{len(text):,} caracteres | {len(text.split()):,} palavras".replace(",", "."))
        self._update_pre_flight_estimate()

    def _update_pre_flight_estimate(self):
        model = self.model_combo.currentData()
        source_text = self.source_editor.toPlainText()
        selected_prods = [p_id for p_id, chk in self.product_checks.items() if chk.isChecked()]
        num_calls = len(selected_prods)

        if not model or num_calls == 0 or not source_text:
            self.lbl_pre_flight.setText(f"Previsão: {num_calls} chamadas | Custo Estimado: $0.000000")
            return

        is_free = bool(model.get("is_free", False))
        est = estimate_pre_flight_cost(
            prompt_chars=len(source_text),
            expected_output_tokens=1500 * num_calls,
            pricing_prompt=model.get("pricing_prompt"),
            pricing_completion=model.get("pricing_completion"),
            pricing_unit=model.get("pricing_unit", "per_1m_tokens"),
            is_free=is_free,
        )

        cost_val = est["estimated_cost_usd"]
        if is_free:
            cost_str = "$0.0000 (Gratuito)"
        elif cost_val is not None:
            cost_str = f"~${cost_val * num_calls:.6f} USD"
        else:
            cost_str = "Preço Desconhecido"

        self.lbl_pre_flight.setText(f"Previsão: {num_calls} chamadas | Custo Estimado: {cost_str}")

    def _select_all_products(self):
        for chk in self.product_checks.values():
            chk.setChecked(True)
        self._update_pre_flight_estimate()

    def _clear_product_selection(self):
        for chk in self.product_checks.values():
            chk.setChecked(False)
        self._update_pre_flight_estimate()

    def _extract_facts(self):
        text = self.source_editor.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "Aviso", "Insira o texto-base da matéria antes de extrair os fatos.")
            return

        facts = extract_facts_heuristic(text)
        self.extracted_facts_cache = facts

        self.facts_table.setRowCount(len(facts))
        for r_idx, f in enumerate(facts):
            chk_item = QTableWidgetItem()
            chk_item.setCheckState(Qt.Checked if f.get("is_pinned", True) else Qt.Unchecked)
            self.facts_table.setItem(r_idx, 0, chk_item)
            self.facts_table.setItem(r_idx, 1, QTableWidgetItem(f.get("source_ref", "")))
            self.facts_table.setItem(r_idx, 2, QTableWidgetItem(f.get("fact", "")))

    def _get_pinned_facts(self) -> List[Dict[str, Any]]:
        pinned = []
        for r_idx in range(self.facts_table.rowCount()):
            chk = self.facts_table.item(r_idx, 0)
            if chk and chk.checkState() == Qt.Checked:
                ref = self.facts_table.item(r_idx, 1).text()
                val = self.facts_table.item(r_idx, 2).text()
                pinned.append({"source_ref": ref, "fact": val, "is_pinned": True})
        return pinned

    def _import_file(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Importar Arquivo de Matéria",
            "",
            "Documentos (*.txt *.docx *.pdf);;Todos os Arquivos (*.*)",
        )
        if file_path:
            try:
                content, title_sug = import_file(Path(file_path))
                self.source_editor.setPlainText(content)
                if not self.title_input.text() or self.title_input.text() == "Nova Matéria Jornalística":
                    self.title_input.setText(title_sug)
                self._extract_facts()
            except ImportErrorWithDiagnostics as ie:
                QMessageBox.warning(self, "Aviso de Importação", str(ie))
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao ler arquivo: {e}")

    def _start_generation(self):
        model = self.model_combo.currentData()
        if not model:
            QMessageBox.warning(self, "Aviso", "Selecione um modelo de IA configurado.")
            return

        source_text = self.source_editor.toPlainText().strip()
        if not source_text:
            QMessageBox.warning(self, "Aviso", "O texto-base da matéria é obrigatório para a geração.")
            return

        selected_prods = [p_id for p_id, chk in self.product_checks.items() if chk.isChecked()]
        if not selected_prods:
            QMessageBox.warning(self, "Aviso", "Selecione ao menos um produto editorial para gerar.")
            return

        # Validação do modo somente gratuitos
        is_strict_free = bool(repo.get_budget_settings().get("strict_free_mode", False)) or (self.profile_combo.currentText() == "Somente Gratuitos")
        if is_strict_free:
            allowed, free_msg = catalog_manager.validate_for_free_mode(model)
            if not allowed:
                QMessageBox.critical(self, "Bloqueio do Modo Somente Gratuitos", free_msg)
                return

        conn = repo.get_connection(model["connection_id"])
        if not conn:
            QMessageBox.critical(self, "Erro", "Conexão associada ao modelo não encontrada.")
            return

        self._auto_save()

        # Preparar visualizadores nas abas de resultados
        for prod_id in selected_prods:
            view = self._get_or_create_result_view(prod_id)
            view.set_content(f"Aguardando geração pelo modelo {model['display_name']}...")

        self.btn_generate.setEnabled(False)
        self.btn_cancel_gen.setEnabled(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setRange(0, len(selected_prods))
        self.progress_bar.setValue(0)

        limit_val = int(self.limit_combo.currentText().replace(".", "").split()[0])
        proj_dict = {
            "id": self.current_project_id,
            "title": self.title_input.text().strip(),
            "raw_text": source_text,
            "extracted_facts": self._get_pinned_facts(),
            "tone": self.tone_combo.currentText(),
            "audience": self.audience_edit.text().strip(),
            "grammatical_person": self.person_combo.currentText(),
            "mandatory_words": self.mandatory_edit.text().strip(),
            "forbidden_expressions": self.forbidden_edit.text().strip(),
            "char_limit_preset": limit_val,
        }

        self.active_generation_worker = GenerationWorker(
            project_data=proj_dict,
            selected_product_ids=selected_prods,
            connection_data=conn,
            model_data=model,
            parent=self,
        )

        self.active_generation_worker.product_started.connect(self._on_worker_product_started)
        self.active_generation_worker.chunk_received.connect(self._on_worker_chunk)
        self.active_generation_worker.product_finished.connect(self._on_worker_product_finished)
        self.active_generation_worker.all_finished.connect(self._on_worker_all_finished)
        self.active_generation_worker.error_occurred.connect(self._on_worker_error)
        self.active_generation_worker.cancelled.connect(self._on_worker_cancelled)

        self.active_generation_worker.start()

    def _get_or_create_result_view(self, product_id: str) -> ProductResultView:
        for idx in range(self.results_tabs.count()):
            tab_widget = self.results_tabs.widget(idx)
            if isinstance(tab_widget, ProductResultView) and tab_widget.product_id == product_id:
                return tab_widget

        # Criar nova aba
        view = ProductResultView(
            product_id=product_id,
            project_id=self.current_project_id,
            on_rewrite_requested=self._handle_rewrite_request,
            parent=self,
        )
        prod_def = EDITORIAL_PRODUCTS.get(product_id)
        tab_name = prod_def.name if prod_def else product_id
        tab_idx = self.results_tabs.addTab(view, tab_name)
        self.results_tabs.setCurrentIndex(tab_idx)
        return view

    def _on_worker_product_started(self, product_id: str, product_name: str):
        view = self._get_or_create_result_view(product_id)
        view.set_content("")  # Limpa para receber streaming

    def _on_worker_chunk(self, product_id: str, chunk_text: str):
        view = self._get_or_create_result_view(product_id)
        view.append_chunk(chunk_text)

    def _on_worker_product_finished(self, product_id: str, result_dict: dict):
        view = self._get_or_create_result_view(product_id)
        view.load_versions()
        self.progress_bar.setValue(self.progress_bar.value() + 1)

    def _on_worker_all_finished(self, count: int, msg: str):
        self.btn_generate.setEnabled(True)
        self.btn_cancel_gen.setEnabled(False)
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "Geração Concluída", msg)

    def _on_worker_error(self, product_id: str, error_msg: str, err_type: str):
        view = self._get_or_create_result_view(product_id)
        view.set_content(f"FALHA NA GERAÇÃO: {error_msg}")
        QMessageBox.warning(self, "Falha Editorial", f"Erro no produto '{product_id}': {error_msg}")

    def _on_worker_cancelled(self):
        self.btn_generate.setEnabled(True)
        self.btn_cancel_gen.setEnabled(False)
        self.progress_bar.setVisible(False)
        QMessageBox.information(self, "Cancelado", "A geração foi interrompida pelo usuário.")

    def _cancel_generation(self):
        if self.active_generation_worker:
            self.active_generation_worker.cancel()

    def _handle_rewrite_request(self, product_id: str, selected_text: str, instruction: str):
        """Dispara a geração de refinamento para o trecho selecionado."""
        model = self.model_combo.currentData()
        conn = repo.get_connection(model["connection_id"])
        if not model or not conn:
            return

        view = self._get_or_create_result_view(product_id)
        view.set_content("Refinando trecho conforme instrução...")

        proj_dict = {
            "id": self.current_project_id,
            "title": self.title_input.text().strip(),
            "raw_text": self.source_editor.toPlainText(),
            "extracted_facts": self._get_pinned_facts(),
            "tone": self.tone_combo.currentText(),
            "audience": self.audience_edit.text().strip(),
            "grammatical_person": self.person_combo.currentText(),
            "char_limit_preset": 1800,
        }

        worker = GenerationWorker(
            project_data=proj_dict,
            selected_product_ids=[product_id],
            connection_data=conn,
            model_data=model,
            custom_instruction=f"REESCRITA DO TRECHO: '{selected_text}'\nINSTRUÇÃO: {instruction}",
            parent=self,
        )
        worker.chunk_received.connect(self._on_worker_chunk)
        worker.product_finished.connect(lambda p_id, res: view.load_versions())
        worker.start()

    def _export_project_zip(self):
        """Exporta todos os produtos atualmente abertos em um pacote ZIP organizado."""
        products_content = {}
        for idx in range(self.results_tabs.count()):
            tab_widget = self.results_tabs.widget(idx)
            if isinstance(tab_widget, ProductResultView):
                content = tab_widget.editor.toPlainText().strip()
                if content:
                    products_content[tab_widget.product_id] = content

        if not products_content:
            QMessageBox.warning(self, "Aviso", "Nenhum produto gerado para empacotar em ZIP.")
            return

        title_slug = self.title_input.text().strip().lower().replace(" ", "_")[:30] or "projeto"
        zip_name = f"{title_slug}_pacote_editorial.zip"

        target_zip, _ = QFileDialog.getSaveFileName(
            self,
            "Salvar Pacote ZIP do Projeto",
            str(paths.exports_dir / zip_name),
            "Arquivo ZIP (*.zip)",
        )
        if target_zip:
            try:
                p = Path(target_zip)
                export_project_zip(p, self.title_input.text().strip(), products_content)
                QMessageBox.information(self, "Pacote Exportado", f"Pacote ZIP gerado com sucesso em:\n{p}")
            except Exception as e:
                QMessageBox.critical(self, "Erro", f"Falha ao gerar ZIP: {e}")
