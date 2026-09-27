"""Adaptador específico para a API da Anthropic Claude (com paginação e streaming SSE nativo)."""

import json
import time
import logging
from typing import Any, Callable, Dict, Iterator, List, Optional
import httpx
from danaurium.providers.base import (
    BaseProvider,
    CatalogModelItem,
    ConnectionTestResult,
    GenerationChunk,
    GenerationRequest,
    UsageData,
    AuthenticationError,
    QuotaExceededError,
    ModelNotFoundError,
    RateLimitError,
    ContextLengthExceededError,
    NetworkTimeoutError,
    ProviderError,
    normalize_url,
    parse_retry_after,
)

logger = logging.getLogger("danaurium.providers.anthropic")

ANTHROPIC_API_VERSION = "2023-06-01"


class AnthropicProvider(BaseProvider):
    """Adaptador dedicado para a API oficial da Anthropic Claude."""

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "anthropic-version": ANTHROPIC_API_VERSION,
            "User-Agent": "DanauriumRedacaoStudio/1.0",
        }
        if self.api_key:
            headers["x-api-key"] = self.api_key
        return headers

    def _handle_error_response(self, response: httpx.Response):
        status = response.status_code
        err_msg = ""
        try:
            body = response.json()
            if "error" in body:
                err_data = body["error"]
                if isinstance(err_data, dict):
                    err_msg = err_data.get("message", "")
                else:
                    err_msg = str(err_data)
        except Exception:
            err_msg = response.text[:300]

        if not err_msg:
            err_msg = f"Erro HTTP {status} retornado pelo servidor Anthropic."

        msg_lower = err_msg.lower()
        if status == 401 or "api key" in msg_lower or "authentication" in msg_lower:
            raise AuthenticationError(f"Falha de autenticação Anthropic: {err_msg}", status_code=status)
        elif status == 402 or "credit balance" in msg_lower or "insufficient" in msg_lower:
            raise QuotaExceededError(f"Saldo insuficiente na conta Anthropic: {err_msg}", status_code=status)
        elif status == 404 or "not found" in msg_lower:
            raise ModelNotFoundError(f"Modelo Anthropic não encontrado: {err_msg}", status_code=status)
        elif status == 429 or "rate_limit" in msg_lower:
            retry_after = parse_retry_after(response.headers.get("retry-after"))
            raise RateLimitError(f"Limite de taxa Anthropic excedido (429): {err_msg}", retry_after=retry_after, status_code=status)
        elif status == 400 and ("prompt is too long" in msg_lower or "context" in msg_lower or "maximum allowed length" in msg_lower):
            raise ContextLengthExceededError(f"Limite de contexto Anthropic excedido: {err_msg}", status_code=status)
        else:
            raise ProviderError(f"Erro na API Anthropic ({status}): {err_msg}", status_code=status)

    def test_connection(self) -> ConnectionTestResult:
        """Testa conectividade consultando a lista de modelos em /v1/models."""
        if not self.api_key:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=0,
                message="Chave de API da Anthropic não informada.",
                details="Insira uma chave válida (x-api-key iniciando por sk-ant-) antes de testar.",
            )

        url = normalize_url(self.base_url, self.catalog_path or "/models")
        start_t = time.time()
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                res = client.get(url, headers=self._get_headers())
                latency = int((time.time() - start_t) * 1000)

                if res.is_success:
                    data = res.json()
                    models = data.get("data", [])
                    return ConnectionTestResult(
                        success=True,
                        status_code=res.status_code,
                        latency_ms=latency,
                        message=f"Conexão com Anthropic validada com sucesso! ({latency} ms)",
                        details=f"Endpoint /v1/models respondeu OK. {len(models)} modelos detectados nesta página.",
                        models_found=len(models),
                    )
                else:
                    self._handle_error_response(res)
        except httpx.TimeoutException:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=int((time.time() - start_t) * 1000),
                message="Tempo limite esgotado ao conectar à Anthropic.",
                details=f"O servidor não respondeu dentro de {self.timeout_seconds} segundos.",
            )
        except httpx.ConnectError as ce:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=int((time.time() - start_t) * 1000),
                message="Falha de rede ao conectar à Anthropic.",
                details=f"Não foi possível alcançar {self.base_url}: {ce}",
            )
        except ProviderError as pe:
            return ConnectionTestResult(
                success=False,
                status_code=pe.status_code,
                latency_ms=int((time.time() - start_t) * 1000),
                message=str(pe),
                details=f"Status: {pe.status_code} | Tipo: {pe.error_type}",
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=int((time.time() - start_t) * 1000),
                message=f"Erro inesperado no teste Anthropic: {e}",
                details=str(e),
            )

    def fetch_catalog(self) -> List[CatalogModelItem]:
        """Consulta modelos da Anthropic com suporte a paginação via after_id."""
        base_endpoint = self.catalog_path or "/models"
        items: List[CatalogModelItem] = []
        after_id = None
        has_more = True

        with httpx.Client(timeout=self.timeout_seconds) as client:
            while has_more:
                url = normalize_url(self.base_url, base_endpoint)
                params = {"limit": 100}
                if after_id:
                    params["after_id"] = after_id

                res = client.get(url, headers=self._get_headers(), params=params)
                if not res.is_success:
                    self._handle_error_response(res)

                data = res.json()
                raw_models = data.get("data", [])
                for m in raw_models:
                    m_id = m.get("id", "")
                    if not m_id:
                        continue
                    display = m.get("display_name") or m_id.replace("-", " ").title()
                    
                    # Identificar capacidades Claude (famílias 3, 3.5, 3.7)
                    context = 200000
                    max_out = 8192 if ("3-5" in m_id or "3-7" in m_id or "sonnet" in m_id) else 4096

                    items.append(CatalogModelItem(
                        model_id=m_id,
                        display_name=display,
                        organization="Anthropic",
                        context_window=context,
                        max_output_tokens=max_out,
                        modalities=["text", "vision"] if "claude-3" in m_id else ["text"],
                        supports_streaming=True,
                        supports_structured_output=True,
                        supported_parameters=["temperature", "top_p", "top_k", "thinking"],
                        pricing_unit="per_1m_tokens",
                        is_free=False,
                    ))

                has_more = bool(data.get("has_more", False))
                after_id = data.get("last_id")
                if not after_id:
                    break

        return sorted(items, key=lambda x: x.display_name)

    def generate_stream(
        self,
        request: GenerationRequest,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Iterator[GenerationChunk]:
        """Gera resposta via Anthropic Messages API (/v1/messages) com streaming Server-Sent Events."""
        endpoint = self.generation_path or "/messages"
        url = normalize_url(self.base_url, endpoint)

        # Montar mensagens no formato estrito da Anthropic
        # A Anthropic exige que mensagens alternem 'user' e 'assistant'
        messages = []
        if request.messages:
            for msg in request.messages:
                role = msg.get("role", "user")
                if role == "system":
                    continue  # Sistema é passado no campo de primeiro nível
                messages.append({"role": role, "content": msg.get("content", "")})
        else:
            messages.append({"role": "user", "content": request.user_prompt})

        payload = {
            "model": request.model_id,
            "max_tokens": request.max_tokens,
            "messages": messages,
            "stream": True,
        }

        # Prompt de sistema passado no campo 'system' de primeiro nível
        if request.system_prompt:
            payload["system"] = request.system_prompt

        # Parâmetro de temperatura
        if request.temperature is not None:
            payload["temperature"] = request.temperature

        attempts = 0
        backoff = 1.0

        while attempts <= self.max_retries:
            attempts += 1
            if cancel_check and cancel_check():
                logger.info("Geração Anthropic cancelada antes do envio.")
                return

            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    with client.stream("POST", url, headers=self._get_headers(), json=payload) as response:
                        if not response.is_success:
                            self._handle_error_response(response)

                        usage_accum = UsageData()

                        for line in response.iter_lines():
                            if cancel_check and cancel_check():
                                logger.info("Streaming Anthropic interrompido pelo usuário.")
                                return

                            if not line or not line.strip():
                                continue

                            line_str = line.strip()
                            if not line_str.startswith("data: "):
                                continue

                            data_str = line_str[6:].strip()
                            try:
                                event = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            event_type = event.get("type")

                            # Capturar tokens de entrada em message_start
                            if event_type == "message_start":
                                msg_data = event.get("message", {})
                                u = msg_data.get("usage", {})
                                usage_accum.input_tokens = u.get("input_tokens", 0)
                                usage_accum.cache_read_tokens = u.get("cache_read_input_tokens", 0)
                                usage_accum.cache_write_tokens = u.get("cache_creation_input_tokens", 0)

                            # Capturar delta de texto
                            elif event_type == "content_block_delta":
                                delta = event.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield GenerationChunk(
                                        text=delta.get("text", ""),
                                        is_final=False,
                                        usage=usage_accum,
                                    )

                            # Capturar finalização e tokens de saída em message_delta
                            elif event_type == "message_delta":
                                u = event.get("usage", {})
                                usage_accum.output_tokens = u.get("output_tokens", usage_accum.output_tokens)
                                stop_reason = event.get("delta", {}).get("stop_reason")
                                yield GenerationChunk(
                                    text="",
                                    is_final=True,
                                    finish_reason=stop_reason or "end_turn",
                                    usage=usage_accum,
                                )

                            elif event_type == "message_stop":
                                yield GenerationChunk(text="", is_final=True, usage=usage_accum)
                                return

                        return

            except RateLimitError as rle:
                if attempts > self.max_retries:
                    raise
                wait_sec = rle.retry_after if rle.retry_after else backoff
                logger.warning("Anthropic Rate limit (429). Aguardando %ss...", wait_sec)
                time.sleep(wait_sec)
                backoff *= 2.0
            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                if attempts > self.max_retries:
                    raise NetworkTimeoutError(f"Falha de conexão com Anthropic após {self.max_retries} tentativas: {net_err}")
                logger.warning("Falha temporária de rede Anthropic (%s). Tentando novamente em %ss...", net_err, backoff)
                time.sleep(backoff)
                backoff *= 2.0
