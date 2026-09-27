"""Fábrica de provedores de IA."""

from typing import Any, Dict, Optional
from danaurium.providers.base import BaseProvider
from danaurium.providers.openai_provider import OpenAIProvider
from danaurium.providers.anthropic_provider import AnthropicProvider
from danaurium.providers.openrouter_provider import OpenRouterProvider
from danaurium.providers.custom_openai import CustomOpenAIProvider


def create_provider(connection_data: Dict[str, Any], api_key: Optional[str] = None) -> BaseProvider:
    """Instancia o adaptador correto com base no tipo de provedor registrado."""
    p_type = (connection_data.get("provider_type") or "openai").lower()

    if p_type == "openai":
        return OpenAIProvider(connection_data, api_key=api_key)
    elif p_type == "anthropic":
        return AnthropicProvider(connection_data, api_key=api_key)
    elif p_type == "openrouter":
        return OpenRouterProvider(connection_data, api_key=api_key)
    elif p_type in ("custom_openai", "custom"):
        return CustomOpenAIProvider(connection_data, api_key=api_key)
    else:
        # Padrão flexível: compatível com OpenAI
        return CustomOpenAIProvider(connection_data, api_key=api_key)
