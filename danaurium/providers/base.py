"""Classes base, modelos de dados e exceções para os adaptadores de provedores de IA."""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, AsyncIterator, Callable, Dict, Iterator, List, Optional
from urllib.parse import urljoin, urlparse

logger = logging.getLogger("danaurium.providers.base")


class ProviderError(Exception):
    """Exceção base para erros em provedores."""
    def __init__(self, message: str, status_code: Optional[int] = None, error_type: str = "general"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_type = error_type


class AuthenticationError(ProviderError):
    """Chave inválida ou credenciais ausentes/expiradas."""
    def __init__(self, message: str, status_code: int = 401):
        super().__init__(message, status_code, "authentication")


class QuotaExceededError(ProviderError):
    """Saldo insuficiente ou cota do provedor esgotada."""
    def __init__(self, message: str, status_code: int = 402):
        super().__init__(message, status_code, "quota_exceeded")


class ModelNotFoundError(ProviderError):
    """Modelo inexistente ou sem permissão de acesso para esta conta."""
    def __init__(self, message: str, status_code: int = 404):
        super().__init__(message, status_code, "model_not_found")


class RateLimitError(ProviderError):
    """Limite de requisições excedido (HTTP 429)."""
    def __init__(self, message: str, retry_after: Optional[int] = None, status_code: int = 429):
        super().__init__(message, status_code, "rate_limit")
        self.retry_after = retry_after


class ContextLengthExceededError(ProviderError):
    """Tamanho do prompt excedeu a janela de contexto suportada pelo modelo."""
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message, status_code, "context_length_exceeded")


class NetworkTimeoutError(ProviderError):
    """Tempo limite de conexão ou leitura esgotado."""
    def __init__(self, message: str):
        super().__init__(message, None, "timeout")


@dataclass
class UsageData:
    """Estatísticas detalhadas de uso de tokens sem dupla contagem."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass
class GenerationRequest:
    """Parâmetros de uma requisição de geração editorial."""
    model_id: str
    user_prompt: str
    system_prompt: Optional[str] = None
    messages: Optional[List[Dict[str, str]]] = None
    temperature: float = 0.7
    max_tokens: int = 2048
    stream: bool = True
    parameters: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerationChunk:
    """Fragmento de texto recebido durante streaming."""
    text: str
    is_final: bool = False
    finish_reason: Optional[str] = None
    usage: Optional[UsageData] = None


@dataclass
class GenerationResult:
    """Resultado final consolidado da geração."""
    text: str
    model_id: str
    latency_ms: int
    usage: UsageData
    finish_reason: Optional[str] = None


@dataclass
class CatalogModelItem:
    """Modelo detectado ou cadastrado para o catálogo."""
    model_id: str
    display_name: str
    organization: Optional[str] = None
    context_window: Optional[int] = None
    max_output_tokens: Optional[int] = None
    modalities: List[str] = field(default_factory=lambda: ["text"])
    supports_streaming: bool = True
    supports_structured_output: bool = True
    supported_parameters: List[str] = field(default_factory=lambda: ["temperature", "top_p"])
    pricing_prompt: Optional[str] = None       # Preço em string decimal por unidade
    pricing_completion: Optional[str] = None   # Preço em string decimal por unidade
    pricing_unit: str = "per_1m_tokens"        # 'per_token', 'per_1k_tokens', 'per_1m_tokens'
    pricing_cache_read: Optional[str] = None
    pricing_cache_write: Optional[str] = None
    pricing_reasoning: Optional[str] = None
    pricing_source: Optional[str] = None
    pricing_updated_at: Optional[str] = None
    is_free: bool = False


@dataclass
class ConnectionTestResult:
    """Resultado detalhado do teste de diagnóstico da conexão."""
    success: bool
    status_code: Optional[int]
    latency_ms: int
    message: str
    details: str
    models_found: int = 0


def normalize_url(base_url: str, path: str) -> str:
    """Combina base_url e path evitando barras duplicadas e duplicações de /v1."""
    base = base_url.rstrip("/")
    p = path.lstrip("/")

    # Evita http://api.com/v1/v1/models se base já terminar com /v1 e p começar com v1/
    if base.endswith("/v1") and p.startswith("v1/"):
        p = p[3:]

    return f"{base}/{p}"


def parse_retry_after(header_val: Optional[str]) -> Optional[int]:
    """Interpreta cabeçalho Retry-After em segundos inteiros."""
    if not header_val:
        return None
    try:
        return int(float(header_val.strip()))
    except ValueError:
        return None


class BaseProvider(ABC):
    """Classe base abstrata para clientes e adaptadores de IA."""

    def __init__(self, connection_data: Dict[str, Any], api_key: Optional[str] = None):
        self.connection_id = connection_data.get("id", "")
        self.name = connection_data.get("name", "")
        self.base_url = connection_data.get("base_url", "").strip()
        self.catalog_path = connection_data.get("catalog_path", "/models").strip()
        self.generation_path = connection_data.get("generation_path", "").strip()
        self.timeout_seconds = int(connection_data.get("timeout_seconds", 60))
        self.max_retries = int(connection_data.get("max_retries", 3))
        self.api_key = api_key

    @abstractmethod
    def test_connection(self) -> ConnectionTestResult:
        """Executa teste de conectividade, autenticação e latência."""
        pass

    @abstractmethod
    def fetch_catalog(self) -> List[CatalogModelItem]:
        """Consulta endpoint oficial de modelos do provedor e retorna catálogo estruturado."""
        pass

    @abstractmethod
    def generate_stream(
        self,
        request: GenerationRequest,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Iterator[GenerationChunk]:
        """Gera resposta via streaming com verificação contínua de cancelamento."""
        pass

    def generate(
        self,
        request: GenerationRequest,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> GenerationResult:
        """Geração síncrona/unificada acumulando chunks de streaming."""
        start_t = time.time()
        full_text = []
        final_usage = UsageData()
        finish_reason = None

        for chunk in self.generate_stream(request, cancel_check=cancel_check):
            if chunk.text:
                full_text.append(chunk.text)
            if chunk.usage:
                final_usage = chunk.usage
            if chunk.finish_reason:
                finish_reason = chunk.finish_reason

        elapsed_ms = int((time.time() - start_t) * 1000)
        return GenerationResult(
            text="".join(full_text),
            model_id=request.model_id,
            latency_ms=elapsed_ms,
            usage=final_usage,
            finish_reason=finish_reason,
        )
