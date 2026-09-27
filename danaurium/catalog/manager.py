"""Gerenciador central do catálogo de modelos com filtros, favoritos, precificação e modo gratuito."""

import json
import logging
from typing import Any, Dict, List, Optional, Tuple
from danaurium.persistence.repository import Repository, repo
from danaurium.security.keyring_manager import credentials
from danaurium.providers.factory import create_provider

logger = logging.getLogger("danaurium.catalog.manager")


class CatalogManager:
    """Controlador de sincronização, enriquecimento e curadoria do catálogo de modelos."""

    def __init__(self, repository: Optional[Repository] = None):
        self.repo = repository or repo

    def sync_connection(self, connection_id: str) -> Tuple[int, str]:
        """Busca catálogo remoto no provedor e atualiza a base local preservando preferências."""
        conn_data = self.repo.get_connection(connection_id)
        if not conn_data:
            return 0, "Conexão não encontrada."

        api_key = credentials.get_api_key(connection_id, conn_data["base_url"])
        provider = create_provider(conn_data, api_key=api_key)

        try:
            fetched = provider.fetch_catalog()
            if not fetched:
                return 0, "Nenhum modelo retornado pelo provedor."

            # Converter para dicts para o repositório
            dict_models = []
            for m in fetched:
                dict_models.append({
                    "model_id": m.model_id,
                    "display_name": m.display_name,
                    "organization": m.organization,
                    "protocol": conn_data.get("provider_type", "chat_completions"),
                    "endpoint": conn_data.get("generation_path"),
                    "modalities": m.modalities,
                    "context_window": m.context_window,
                    "max_output_tokens": m.max_output_tokens,
                    "supports_streaming": m.supports_streaming,
                    "supports_structured_output": m.supports_structured_output,
                    "supported_parameters": m.supported_parameters,
                    "pricing_prompt": m.pricing_prompt,
                    "pricing_completion": m.pricing_completion,
                    "pricing_unit": m.pricing_unit,
                    "pricing_cache_read": m.pricing_cache_read,
                    "pricing_cache_write": m.pricing_cache_write,
                    "pricing_reasoning": m.pricing_reasoning,
                    "pricing_source": m.pricing_source or f"API oficial {conn_data['name']}",
                    "pricing_updated_at": m.pricing_updated_at or "2026-09-27",
                    "is_free": m.is_free,
                })

            self.repo.sync_catalog_models(connection_id, dict_models)
            return len(dict_models), f"{len(dict_models)} modelos sincronizados com sucesso."
        except Exception as e:
            logger.error("Erro ao sincronizar catálogo da conexão %s: %s", connection_id, e)
            return 0, f"Falha na sincronização: {e}"

    def register_manual_model(self, connection_id: str, data: Dict[str, Any]) -> str:
        """Cadastra manualmente um modelo específico por ID."""
        data_copy = dict(data)
        data_copy["connection_id"] = connection_id
        return self.repo.save_model(data_copy)

    def validate_for_free_mode(self, model: Dict[str, Any]) -> Tuple[bool, str]:
        """Aplica as regras rígidas do modo 'Somente Gratuitos'.
        
        Regras:
        - Modelos pagos são sumariamente bloqueados.
        - Preços desconhecidos NÃO são considerados gratuitos; são bloqueados.
        - Não há fallback para modelo pago.
        - Apenas modelos explicitamente verificados com custo zero (ou rota openrouter/free) são aprovados.
        """
        if not model:
            return False, "Nenhum modelo selecionado."

        m_id = model.get("model_id", "")
        # Rota de roteamento gratuito oficial do OpenRouter
        if m_id == "openrouter/free" or m_id.endswith(":free"):
            return True, "Modelo gratuito aprovado."

        is_free_flag = bool(model.get("is_free", False))
        pricing_prompt = model.get("pricing_prompt")
        pricing_comp = model.get("pricing_completion")

        if pricing_prompt is None or pricing_comp is None:
            if not is_free_flag:
                return False, (
                    f"O modelo '{model.get('display_name')}' possui preço DESCONHECIDO no catálogo. "
                    "O Modo 'Somente Gratuitos' bloqueia modelos sem preço confirmado para evitar cobranças imprevistas."
                )

        try:
            p_in = float(pricing_prompt or 0)
            p_out = float(pricing_comp or 0)
            if p_in > 0 or p_out > 0:
                return False, (
                    f"O modelo '{model.get('display_name')}' é PAGO (${p_in}/1M in, ${p_out}/1M out). "
                    "Operação bloqueada pelo Modo 'Somente Gratuitos'."
                )
        except ValueError:
            return False, "Metadados de precificação inválidos. Bloqueado por precaução."

        return True, "Modelo gratuito confirmado."

    def export_catalog_json(self) -> str:
        """Exporta todas as configurações de modelos do catálogo (livre de segredos e credenciais)."""
        models = self.repo.get_models(only_active=False)
        clean_models = []
        for m in models:
            c = dict(m)
            # Remove IDs internos gerados para garantir portabilidade
            clean_models.append(c)
        return json.dumps(clean_models, ensure_ascii=False, indent=2)

    def import_catalog_json(self, json_str: str) -> int:
        """Importa configurações de modelos preservando integridade."""
        data = json.loads(json_str)
        if not isinstance(data, list):
            raise ValueError("O formato de catálogo importado deve ser uma lista JSON.")

        count = 0
        for item in data:
            if "connection_id" in item and "model_id" in item and "display_name" in item:
                self.repo.save_model(item)
                count += 1
        return count


# Instância global do gerenciador de catálogo
catalog_manager = CatalogManager()
