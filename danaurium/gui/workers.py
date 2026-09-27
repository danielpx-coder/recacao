"""Trabalhadores em segundo plano (QThread / Signals) para manter a interface desktop sempre fluida."""

import time
import logging
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional
from PySide6.QtCore import QThread, Signal
from danaurium.providers.factory import create_provider
from danaurium.providers.base import GenerationRequest, UsageData
from danaurium.security.keyring_manager import credentials
from danaurium.editorial.rules import build_generation_prompts
from danaurium.editorial.fidelity import verify_editorial_fidelity
from danaurium.catalog.pricing import calculate_cost_usd
from danaurium.budget.manager import budget_manager
from danaurium.persistence.repository import repo

logger = logging.getLogger("danaurium.gui.workers")


class GenerationWorker(QThread):
    """Executa a geração de um ou mais produtos editoriais em segundo plano com suporte a streaming e cancelamento."""

    # Sinais para comunicação segura com a interface
    product_started = Signal(str, str)              # (product_id, product_name)
    chunk_received = Signal(str, str)               # (product_id, chunk_text)
    product_finished = Signal(str, dict)            # (product_id, result_dict)
    all_finished = Signal(int, str)                 # (total_success, summary_message)
    error_occurred = Signal(str, str, str)          # (product_id, error_message, error_type)
    cancelled = Signal()

    def __init__(
        self,
        project_data: Dict[str, Any],
        selected_product_ids: List[str],
        connection_data: Dict[str, Any],
        model_data: Dict[str, Any],
        custom_instruction: Optional[str] = None,
        parent=None,
    ):
        super().__init__(parent)
        self.project_data = dict(project_data)
        self.selected_product_ids = list(selected_product_ids)
        self.connection_data = dict(connection_data)
        self.model_data = dict(model_data)
        self.custom_instruction = custom_instruction
        self._is_cancelled = False

    def cancel(self):
        """Sinaliza cancelamento imediato."""
        self._is_cancelled = True
        logger.info("Solicitação de cancelamento recebida pelo GenerationWorker.")

    def is_cancelled(self) -> bool:
        return self._is_cancelled

    def run(self):
        total_products = len(self.selected_product_ids)
        successful_count = 0

        conn_id = self.connection_data["id"]
        base_url = self.connection_data["base_url"]
        api_key = credentials.get_api_key(conn_id, base_url)
        model_id = self.model_data["model_id"]
        is_free_model = bool(self.model_data.get("is_free", False))

        provider = create_provider(self.connection_data, api_key=api_key)

        for prod_id in self.selected_product_ids:
            if self._is_cancelled:
                self.cancelled.emit()
                return

            self.product_started.emit(prod_id, prod_id)

            # 1. Alocar reserva de orçamento prévia
            res_id = f"res_{int(time.time()*1000)}_{prod_id}"
            est_cost = Decimal("0.000000") if is_free_model else Decimal("0.002000")
            allowed, budget_msg = budget_manager.reserve_budget(
                reservation_id=res_id,
                estimated_cost_usd=est_cost,
                project_id=self.project_data.get("id"),
                is_free=is_free_model,
            )

            if not allowed:
                self.error_occurred.emit(prod_id, f"Bloqueio de orçamento: {budget_msg}", "budget_limit")
                continue

            try:
                # 2. Construir prompts com contexto seguro e diretrizes de estilo
                prompts = build_generation_prompts(
                    product_id=prod_id,
                    project_data=self.project_data,
                    custom_instruction=self.custom_instruction,
                )

                req = GenerationRequest(
                    model_id=model_id,
                    system_prompt=prompts["system_prompt"],
                    user_prompt=prompts["user_prompt"],
                    temperature=0.7,
                    max_tokens=self.model_data.get("max_output_tokens") or 2048,
                    stream=True,
                )

                start_t = time.time()
                accumulated_text = []
                final_usage = UsageData()
                finish_reason = None

                # 3. Stream com verificação contínua de cancelamento
                for chunk in provider.generate_stream(req, cancel_check=self.is_cancelled):
                    if self._is_cancelled:
                        budget_manager.release_reservation(res_id)
                        self.cancelled.emit()
                        return

                    if chunk.text:
                        accumulated_text.append(chunk.text)
                        self.chunk_received.emit(prod_id, chunk.text)
                    if chunk.usage:
                        final_usage = chunk.usage
                    if chunk.finish_reason:
                        finish_reason = chunk.finish_reason

                elapsed_ms = int((time.time() - start_t) * 1000)
                full_content = "".join(accumulated_text)

                # Se a API não retornou contagem exata no stream, estimar tokens
                if final_usage.output_tokens == 0 and full_content:
                    final_usage.output_tokens = max(1, int(len(full_content) / 3.8))
                if final_usage.input_tokens == 0:
                    final_usage.input_tokens = max(1, int(len(prompts["user_prompt"]) / 3.8))

                # 4. Calcular custo financeiro exato com aritmética decimal
                cost_dec, is_known_price = calculate_cost_usd(
                    input_tokens=final_usage.input_tokens,
                    output_tokens=final_usage.output_tokens,
                    pricing_prompt=self.model_data.get("pricing_prompt"),
                    pricing_completion=self.model_data.get("pricing_completion"),
                    pricing_unit=self.model_data.get("pricing_unit", "per_1m_tokens"),
                    cache_read_tokens=final_usage.cache_read_tokens,
                    pricing_cache_read=self.model_data.get("pricing_cache_read"),
                    reasoning_tokens=final_usage.reasoning_tokens,
                    pricing_reasoning=self.model_data.get("pricing_reasoning"),
                )
                if is_free_model:
                    cost_dec = Decimal("0.000000")

                cost_str = f"{cost_dec:.6f}" if cost_dec is not None else "0.000000"

                # 5. Verificação determinística de fidelidade editorial
                fidelity_warnings = verify_editorial_fidelity(
                    source_text=self.project_data.get("raw_text", ""),
                    generated_text=full_content,
                    mandatory_words=self.project_data.get("mandatory_words", ""),
                    forbidden_expressions=self.project_data.get("forbidden_expressions", ""),
                    max_char_limit=self.project_data.get("char_limit_preset"),
                )

                # 6. Salvar versão no banco de dados SQLite
                proj_id = self.project_data.get("id")
                if proj_id:
                    ver_id = repo.save_version({
                        "project_id": proj_id,
                        "product_id": prod_id,
                        "title": f"{self.project_data.get('title', 'Matéria')} - {prod_id}",
                        "content": full_content,
                        "model_used": model_id,
                        "connection_used": conn_id,
                        "prompt_instruction": self.custom_instruction,
                        "fidelity_warnings": fidelity_warnings,
                        "word_count": len(full_content.split()),
                        "char_count": len(full_content),
                        "latency_ms": elapsed_ms,
                        "tokens_input": final_usage.input_tokens,
                        "tokens_output": final_usage.output_tokens,
                        "tokens_reasoning": final_usage.reasoning_tokens,
                        "tokens_cache": final_usage.cache_read_tokens,
                        "cost_calculated": cost_str,
                    })

                    # Registrar log de consumo e faturamento
                    repo.log_usage({
                        "project_id": proj_id,
                        "connection_id": conn_id,
                        "model_id": model_id,
                        "task_type": "redacao",
                        "product_id": prod_id,
                        "pre_flight_estimate": str(est_cost),
                        "tokens_input": final_usage.input_tokens,
                        "tokens_output": final_usage.output_tokens,
                        "tokens_cache_read": final_usage.cache_read_tokens,
                        "tokens_cache_write": final_usage.cache_write_tokens,
                        "tokens_reasoning": final_usage.reasoning_tokens,
                        "cost_calculated": cost_str,
                        "latency_ms": elapsed_ms,
                        "status": "success",
                    })

                # Notificar conclusão do produto
                result_dict = {
                    "product_id": prod_id,
                    "content": full_content,
                    "latency_ms": elapsed_ms,
                    "tokens_input": final_usage.input_tokens,
                    "tokens_output": final_usage.output_tokens,
                    "tokens_reasoning": final_usage.reasoning_tokens,
                    "cost_calculated_usd": cost_dec,
                    "fidelity_warnings": fidelity_warnings,
                }
                self.product_finished.emit(prod_id, result_dict)
                successful_count += 1

            except Exception as e:
                logger.error("Erro durante geração de %s: %s", prod_id, e)
                self.error_occurred.emit(prod_id, str(e), getattr(e, "error_type", "exception"))
            finally:
                budget_manager.release_reservation(res_id)

        self.all_finished.emit(successful_count, f"{successful_count} de {total_products} produtos gerados com sucesso.")


class ConnectionTestWorker(QThread):
    """Executa diagnóstico e teste de conexão com o provedor em segundo plano."""
    finished = Signal(dict)

    def __init__(self, connection_data: Dict[str, Any], parent=None):
        super().__init__(parent)
        self.connection_data = connection_data

    def run(self):
        conn_id = self.connection_data["id"]
        base_url = self.connection_data["base_url"]
        api_key = credentials.get_api_key(conn_id, base_url)
        provider = create_provider(self.connection_data, api_key=api_key)
        res = provider.test_connection()
        self.finished.emit({
            "success": res.success,
            "status_code": res.status_code,
            "latency_ms": res.latency_ms,
            "message": res.message,
            "details": res.details,
            "models_found": res.models_found,
        })


class CatalogSyncWorker(QThread):
    """Sincroniza o catálogo de modelos remotamente em segundo plano."""
    finished = Signal(int, str)

    def __init__(self, connection_id: str, parent=None):
        super().__init__(parent)
        self.connection_id = connection_id

    def run(self):
        from danaurium.catalog.manager import catalog_manager
        count, msg = catalog_manager.sync_connection(self.connection_id)
        self.finished.emit(count, msg)


class CompareLabWorker(QThread):
    """Executa a mesma tarefa jornalística em 2 ou 3 modelos simultaneamente para comparação lado a lado."""
    model_started = Signal(str)
    model_finished = Signal(str, dict)
    all_finished = Signal()
    error_occurred = Signal(str, str)

    def __init__(
        self,
        task_prompt: str,
        system_prompt: str,
        models_configs: List[Dict[str, Any]],  # List of {connection_data, model_data}
        parent=None,
    ):
        super().__init__(parent)
        self.task_prompt = task_prompt
        self.system_prompt = system_prompt
        self.models_configs = models_configs
        self._is_cancelled = False

    def cancel(self):
        self._is_cancelled = True

    def run(self):
        for item in self.models_configs:
            if self._is_cancelled:
                break
            conn_data = item["connection_data"]
            model_data = item["model_data"]
            model_key = f"{conn_data['id']}::{model_data['model_id']}"

            self.model_started.emit(model_key)
            api_key = credentials.get_api_key(conn_data["id"], conn_data["base_url"])
            provider = create_provider(conn_data, api_key=api_key)

            req = GenerationRequest(
                model_id=model_data["model_id"],
                system_prompt=self.system_prompt,
                user_prompt=self.task_prompt,
                temperature=0.7,
                max_tokens=2048,
                stream=False,
            )

            try:
                gen_res = provider.generate(req, cancel_check=lambda: self._is_cancelled)
                cost_dec, _ = calculate_cost_usd(
                    input_tokens=gen_res.usage.input_tokens,
                    output_tokens=gen_res.usage.output_tokens,
                    pricing_prompt=model_data.get("pricing_prompt"),
                    pricing_completion=model_data.get("pricing_completion"),
                    pricing_unit=model_data.get("pricing_unit", "per_1m_tokens"),
                )
                self.model_finished.emit(model_key, {
                    "model_display": model_data.get("display_name", model_data["model_id"]),
                    "text": gen_res.text,
                    "latency_ms": gen_res.latency_ms,
                    "usage": gen_res.usage,
                    "cost_usd": cost_dec,
                })
            except Exception as e:
                self.error_occurred.emit(model_key, str(e))

        self.all_finished.emit()
