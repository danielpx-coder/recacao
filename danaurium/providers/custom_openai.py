"""Adaptador para conexões personalizadas compatíveis com o protocolo OpenAI Chat Completions."""

import logging
from typing import Any, Dict, Optional
from danaurium.providers.openai_provider import OpenAIProvider
from danaurium.providers.base import ConnectionTestResult

logger = logging.getLogger("danaurium.providers.custom")


class CustomOpenAIProvider(OpenAIProvider):
    """Adaptador para servidores locais ou provedores terceiros compatíveis com OpenAI.
    
    Exemplos: Ollama, LM Studio, vLLM, LocalAI, Mistral API, Groq, Together, etc.
    """

    def test_connection(self) -> ConnectionTestResult:
        res = super().test_connection()
        if res.success:
            res.details = (
                f"{res.details}\n"
                "Aviso de compatibilidade: O servidor respondeu ao endpoint de catálogo. "
                "Certifique-se de que o endpoint de geração suporte a especificação padrão OpenAI Chat Completions."
            )
        return res
