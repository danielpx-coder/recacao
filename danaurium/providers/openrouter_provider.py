"""Adaptador completo para OpenRouter (com suporte a openrouter/free, catálogo e precificação)."""

import json
import time
import logging
from decimal import Decimal
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

logger = logging.getLogger("danaurium.providers.openrouter")


class OpenRouterProvider(BaseProvider):
    """Adaptador para o agregador OpenRouter."""

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "HTTP-Referer": "https://danaurium.com.br",
            "X-Title": "Danaurium Redacao Studio",
            "User-Agent": "DanauriumRedacaoStudio/1.0",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
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
            err_msg = f"Erro HTTP {status} retornado pelo servidor OpenRouter."

        msg_lower = err_msg.lower()
        if status == 401 or "unauthorized" in msg_lower or "api key" in msg_lower:
            raise AuthenticationError(f"Falha de autenticação OpenRouter: {err_msg}", status_code=status)
        elif status == 402 or "credits" in msg_lower or "insufficient" in msg_lower or "balance" in msg_lower:
            raise QuotaExceededError(f"Créditos insuficientes no OpenRouter: {err_msg}", status_code=status)
        elif status == 404:
            raise ModelNotFoundError(f"Modelo OpenRouter não encontrado: {err_msg}", status_code=status)
        elif status == 429:
            retry_after = parse_retry_after(response.headers.get("retry-after"))
            raise RateLimitError(f"Limite OpenRouter excedido (429): {err_msg}", retry_after=retry_after, status_code=status)
        elif status == 400 and ("context length" in msg_lower or "maximum context" in msg_lower):
            raise ContextLengthExceededError(f"Limite de contexto do modelo OpenRouter excedido: {err_msg}", status_code=status)
        else:
            raise ProviderError(f"Erro na API OpenRouter ({status}): {err_msg}", status_code=status)

    def test_connection(self) -> ConnectionTestResult:
        """Testa conexão listando modelos em /models."""
        if not self.api_key:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=0,
                message="Chave de API do OpenRouter não informada.",
                details="Insira uma chave válida (sk-or-v1-...) antes de testar a conexão.",
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
                        message=f"Conexão com OpenRouter bem-sucedida! ({latency} ms)",
                        details=f"Catálogo retornou {len(models)} modelos com metadados e preços.",
                        models_found=len(models),
                    )
                else:
                    self._handle_error_response(res)
        except httpx.TimeoutException:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=int((time.time() - start_t) * 1000),
                message="Tempo limite esgotado ao contatar OpenRouter.",
                details=f"O servidor não respondeu dentro de {self.timeout_seconds} segundos.",
            )
        except httpx.ConnectError as ce:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=int((time.time() - start_t) * 1000),
                message="Falha de conexão com OpenRouter.",
                details=f"Não foi possível alcançar {self.base_url}: {ce}",
            )
        except ProviderError as pe:
            return ConnectionTestResult(
                success=False,
                status_code=pe.status_code,
                latency_ms=int((time.time() - start_t) * 1000),
                message=str(pe),
                details=f"Tipo de erro: {pe.error_type} ({pe.status_code})",
            )
        except Exception as e:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=int((time.time() - start_t) * 1000),
                message=f"Erro inesperado: {e}",
                details=str(e),
            )

    def fetch_catalog(self) -> List[CatalogModelItem]:
        """Obtém modelos da API OpenRouter com preços reais e identificação do roteador gratuito."""
        url = normalize_url(self.base_url, self.catalog_path or "/models")
        with httpx.Client(timeout=self.timeout_seconds) as client:
            res = client.get(url, headers=self._get_headers())
            if not res.is_success:
                self._handle_error_response(res)

            data = res.json()
            raw_models = data.get("data", [])
            items: List[CatalogModelItem] = []

            # 1. Adicionar o Roteador Gratuito Oficial da OpenRouter
            items.append(CatalogModelItem(
                model_id="openrouter/free",
                display_name="OpenRouter: Free Models Router (Seleção Automática)",
                organization="OpenRouter",
                context_window=131072,
                max_output_tokens=4096,
                modalities=["text"],
                supports_streaming=True,
                supports_structured_output=True,
                supported_parameters=["temperature", "top_p"],
                pricing_prompt="0.000000",
                pricing_completion="0.000000",
                pricing_unit="per_1m_tokens",
                pricing_source="OpenRouter Free Models Router Oficial",
                pricing_updated_at="2026-09-27",
                is_free=True,
            ))

            for m in raw_models:
                m_id = m.get("id", "")
                if not m_id:
                    continue

                display = m.get("name") or m_id
                pricing = m.get("pricing") or {}
                prompt_p_token = pricing.get("prompt")
                comp_p_token = pricing.get("completion")

                # Conversão de preço por token para preço por 1 milhão de tokens (USD)
                # OpenRouter fornece valores por token (ex: 0.0000025)
                pricing_prompt_1m = None
                pricing_comp_1m = None
                is_free = False

                if prompt_p_token is not None and comp_p_token is not None:
                    try:
                        p_dec = Decimal(str(prompt_p_token))
                        c_dec = Decimal(str(comp_p_token))
                        if p_dec == 0 and c_dec == 0:
                            is_free = True
                            pricing_prompt_1m = "0.000000"
                            pricing_comp_1m = "0.000000"
                        else:
                            pricing_prompt_1m = str((p_dec * Decimal("1000000")).quantize(Decimal("0.000001")))
                            pricing_comp_1m = str((c_dec * Decimal("1000000")).quantize(Decimal("0.000001")))
                    except Exception:
                        pass

                if m_id.endswith(":free"):
                    is_free = True
                    if not pricing_prompt_1m:
                        pricing_prompt_1m = "0.000000"
                        pricing_comp_1m = "0.000000"

                top_provider = m.get("top_provider") or {}
                max_out = top_provider.get("max_completion_tokens") or 4096

                # Extrair organização a partir do namespace do modelo (ex: 'meta-llama/...' -> 'Meta')
                org = m_id.split("/")[0].title() if "/" in m_id else "OpenRouter"

                items.append(CatalogModelItem(
                    model_id=m_id,
                    display_name=display,
                    organization=org,
                    context_window=m.get("context_length", 32768),
                    max_output_tokens=max_out,
                    modalities=["text"],
                    supports_streaming=True,
                    supports_structured_output=True,
                    supported_parameters=["temperature", "top_p"],
                    pricing_prompt=pricing_prompt_1m,
                    pricing_completion=pricing_comp_1m,
                    pricing_unit="per_1m_tokens",
                    pricing_source="OpenRouter API",
                    pricing_updated_at="2026-09-27",
                    is_free=is_free,
                ))

            return sorted(items, key=lambda x: (not x.is_free, x.display_name))

    def generate_stream(
        self,
        request: GenerationRequest,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Iterator[GenerationChunk]:
        """Gera resposta via OpenRouter Chat Completions (/chat/completions) com streaming SSE."""
        endpoint = self.generation_path or "/chat/completions"
        url = normalize_url(self.base_url, endpoint)

        messages = []
        if request.system_prompt:
            messages.append({"role": "system", "content": request.system_prompt})
        if request.messages:
            messages.extend(request.messages)
        else:
            messages.append({"role": "user", "content": request.user_prompt})

        payload = {
            "model": request.model_id,
            "messages": messages,
            "stream": True,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        attempts = 0
        backoff = 1.0

        while attempts <= self.max_retries:
            attempts += 1
            if cancel_check and cancel_check():
                logger.info("Geração OpenRouter cancelada antes do envio.")
                return

            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    with client.stream("POST", url, headers=self._get_headers(), json=payload) as response:
                        if not response.is_success:
                            self._handle_error_response(response)

                        usage_accum = UsageData()

                        for line in response.iter_lines():
                            if cancel_check and cancel_check():
                                logger.info("Streaming OpenRouter interrompido pelo usuário.")
                                return

                            if not line or not line.strip():
                                continue

                            line_str = line.strip()
                            if not line_str.startswith("data: "):
                                continue

                            data_str = line_str[6:].strip()
                            if data_str == "[DONE]":
                                yield GenerationChunk(text="", is_final=True, usage=usage_accum)
                                return

                            try:
                                chunk_json = json.loads(data_str)
                            except json.JSONDecodeError:
                                continue

                            # Capturar uso retornado no chunk
                            if "usage" in chunk_json and chunk_json["usage"]:
                                u = chunk_json["usage"]
                                usage_accum.input_tokens = u.get("prompt_tokens", usage_accum.input_tokens)
                                usage_accum.output_tokens = u.get("completion_tokens", usage_accum.output_tokens)

                            choices = chunk_json.get("choices", [])
                            if choices:
                                c = choices[0]
                                finish_reason = c.get("finish_reason")
                                delta = c.get("delta", {})
                                delta_text = delta.get("content", "") or ""
                                if delta_text or finish_reason:
                                    yield GenerationChunk(
                                        text=delta_text,
                                        is_final=(finish_reason is not None and finish_reason != ""),
                                        finish_reason=finish_reason,
                                        usage=usage_accum,
                                    )

                        yield GenerationChunk(text="", is_final=True, usage=usage_accum)
                        return

            except RateLimitError as rle:
                if attempts > self.max_retries:
                    raise
                wait_sec = rle.retry_after if rle.retry_after else backoff
                logger.warning("Rate limit OpenRouter (429). Aguardando %ss...", wait_sec)
                time.sleep(wait_sec)
                backoff *= 2.0
            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                if attempts > self.max_retries:
                    raise NetworkTimeoutError(f"Falha de rede com OpenRouter após {self.max_retries} tentativas: {net_err}")
                logger.warning("Falha temporária de rede OpenRouter (%s). Aguardando %ss...", net_err, backoff)
                time.sleep(backoff)
                backoff *= 2.0
