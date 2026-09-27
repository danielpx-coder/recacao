"""Adaptador para a API da OpenAI (suporte a /models, /chat/completions e /responses)."""

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

logger = logging.getLogger("danaurium.providers.openai")


class OpenAIProvider(BaseProvider):
    """Adaptador para o ecossistema oficial da OpenAI."""

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
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
            err_msg = f"Erro HTTP {status} retornado pelo servidor."

        if status == 401:
            raise AuthenticationError(f"Falha de autenticação OpenAI: {err_msg}", status_code=status)
        elif status == 402:
            raise QuotaExceededError(f"Cota ou saldo insuficiente na OpenAI: {err_msg}", status_code=status)
        elif status == 404:
            raise ModelNotFoundError(f"Recurso ou modelo OpenAI não encontrado: {err_msg}", status_code=status)
        elif status == 429:
            retry_after = parse_retry_after(response.headers.get("retry-after"))
            raise RateLimitError(f"Limite de requisições OpenAI excedido (429): {err_msg}", retry_after=retry_after, status_code=status)
        elif status == 400 and ("context_length" in err_msg.lower() or "maximum context" in err_msg.lower()):
            raise ContextLengthExceededError(f"Contexto do modelo OpenAI excedido: {err_msg}", status_code=status)
        else:
            raise ProviderError(f"Erro na API OpenAI ({status}): {err_msg}", status_code=status)

    def test_connection(self) -> ConnectionTestResult:
        """Testa conexão listando modelos em /models."""
        if not self.api_key:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=0,
                message="Chave de API não informada para esta conexão.",
                details="Configure uma chave de API válida para a OpenAI antes de testar.",
            )

        url = normalize_url(self.base_url, self.catalog_path)
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
                        message=f"Conexão com OpenAI estabelecida com sucesso! ({latency} ms)",
                        details=f"Endpoint respondeu OK (200). {len(models)} modelos disponíveis no catálogo.",
                        models_found=len(models),
                    )
                else:
                    self._handle_error_response(res)
        except httpx.TimeoutException:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=int((time.time() - start_t) * 1000),
                message="Tempo limite esgotado ao conectar à OpenAI.",
                details=f"O servidor não respondeu dentro de {self.timeout_seconds}s.",
            )
        except httpx.ConnectError as ce:
            return ConnectionTestResult(
                success=False,
                status_code=None,
                latency_ms=int((time.time() - start_t) * 1000),
                message="Falha de rede ao conectar à OpenAI.",
                details=f"Não foi possível alcançar o servidor {self.base_url}: {ce}",
            )
        except ProviderError as pe:
            return ConnectionTestResult(
                success=False,
                status_code=pe.status_code,
                latency_ms=int((time.time() - start_t) * 1000),
                message=str(pe),
                details=f"Tipo de erro: {pe.error_type} (HTTP {pe.status_code})",
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
        """Obtém lista de modelos a partir de /models."""
        url = normalize_url(self.base_url, self.catalog_path)
        with httpx.Client(timeout=self.timeout_seconds) as client:
            res = client.get(url, headers=self._get_headers())
            if not res.is_success:
                self._handle_error_response(res)

            data = res.json()
            raw_models = data.get("data", [])
            items = []

            for m in raw_models:
                m_id = m.get("id", "")
                if not m_id:
                    continue
                
                # Filtrar modelos que não são de texto/chat (como embeddings, tts, whisper, dall-e)
                # para manter o catálogo relevante ao jornalista
                m_lower = m_id.lower()
                if any(p in m_lower for p in ["embed", "tts", "whisper", "dall-e", "moderation", "babbage", "davinci"]):
                    continue

                display = m_id.replace("-", " ").title()
                org = m.get("owned_by", "openai")

                # Context window estimado conforme famílias conhecidas da OpenAI
                context = 128000 if ("gpt-4o" in m_lower or "o1" in m_lower or "o3" in m_lower) else 16384
                max_out = 16384 if ("gpt-4o" in m_lower or "o1" in m_lower) else 4096

                # Parâmetros suportados
                params = ["temperature", "top_p", "presence_penalty", "frequency_penalty"]
                if "o1" in m_lower or "o3" in m_lower:
                    params.append("reasoning_effort")

                items.append(CatalogModelItem(
                    model_id=m_id,
                    display_name=display,
                    organization=org,
                    context_window=context,
                    max_output_tokens=max_out,
                    modalities=["text"],
                    supports_streaming=True,
                    supports_structured_output=True,
                    supported_parameters=params,
                    pricing_unit="per_1m_tokens",
                    is_free=False,
                ))

            return sorted(items, key=lambda x: x.display_name)

    def generate_stream(
        self,
        request: GenerationRequest,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Iterator[GenerationChunk]:
        """Gera resposta em streaming com suporte aos endpoints /responses e /chat/completions."""
        endpoint = self.generation_path or "/chat/completions"
        is_responses_api = "/responses" in endpoint

        url = normalize_url(self.base_url, endpoint)

        # Montar payload conforme o protocolo selecionado
        if is_responses_api:
            # Novo endpoint /v1/responses da OpenAI
            input_items = []
            if request.system_prompt:
                input_items.append({"role": "developer", "content": request.system_prompt})
            if request.messages:
                for msg in request.messages:
                    input_items.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            else:
                input_items.append({"role": "user", "content": request.user_prompt})

            payload = {
                "model": request.model_id,
                "input": input_items,
                "stream": request.stream,
            }
            if "temperature" in request.parameters:
                payload["temperature"] = request.parameters["temperature"]
            elif request.temperature is not None:
                payload["temperature"] = request.temperature
        else:
            # Protocolo padrão Chat Completions
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
                "stream": request.stream,
                "stream_options": {"include_usage": True},
            }
            # Parâmetros especiais para modelos de raciocínio (o1/o3 não aceitam max_tokens nem temperature em certas versões)
            is_reasoning_model = any(tag in request.model_id.lower() for tag in ["o1-", "o3-", "o1", "o3"])
            if not is_reasoning_model:
                payload["temperature"] = request.temperature
                payload["max_tokens"] = request.max_tokens
            else:
                payload["max_completion_tokens"] = request.max_tokens

        # Execução com política de repetição progressiva (exponential backoff)
        attempts = 0
        backoff = 1.0

        while attempts <= self.max_retries:
            attempts += 1
            if cancel_check and cancel_check():
                logger.info("Geração cancelada pelo usuário antes da chamada.")
                return

            try:
                with httpx.Client(timeout=self.timeout_seconds) as client:
                    with client.stream("POST", url, headers=self._get_headers(), json=payload) as response:
                        if not response.is_success:
                            self._handle_error_response(response)

                        # Processar streaming SSE
                        usage_accum = UsageData()

                        for line in response.iter_lines():
                            if cancel_check and cancel_check():
                                logger.info("Streaming cancelado pelo usuário durante recebimento.")
                                return

                            if not line or not line.strip():
                                continue

                            line_str = line.strip()
                            if line_str.startswith("data: "):
                                data_str = line_str[6:].strip()
                                if data_str == "[DONE]":
                                    yield GenerationChunk(text="", is_final=True, usage=usage_accum)
                                    return

                                try:
                                    chunk_json = json.loads(data_str)
                                except json.JSONDecodeError:
                                    continue

                                # Capturar tokens de uso
                                if "usage" in chunk_json and chunk_json["usage"]:
                                    u = chunk_json["usage"]
                                    usage_accum.input_tokens = u.get("prompt_tokens", usage_accum.input_tokens)
                                    usage_accum.output_tokens = u.get("completion_tokens", usage_accum.output_tokens)
                                    prompt_details = u.get("prompt_tokens_details") or {}
                                    usage_accum.cache_read_tokens = prompt_details.get("cached_tokens", 0)
                                    comp_details = u.get("completion_tokens_details") or {}
                                    usage_accum.reasoning_tokens = comp_details.get("reasoning_tokens", 0)

                                # Extrair texto do chunk
                                delta_text = ""
                                finish_reason = None

                                if is_responses_api:
                                    # Formato /responses
                                    event_type = chunk_json.get("type")
                                    if event_type == "response.text.delta":
                                        delta_text = chunk_json.get("delta", "")
                                    elif event_type == "response.completed":
                                        finish_reason = "completed"
                                else:
                                    # Formato Chat Completions
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

                        # Finalização normal do stream
                        yield GenerationChunk(text="", is_final=True, usage=usage_accum)
                        return

            except RateLimitError as rle:
                if attempts > self.max_retries:
                    raise
                wait_sec = rle.retry_after if rle.retry_after else backoff
                logger.warning("Rate limit atingido (429). Aguardando %ss antes de nova tentativa...", wait_sec)
                time.sleep(wait_sec)
                backoff *= 2.0
            except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                if attempts > self.max_retries:
                    raise NetworkTimeoutError(f"Falha de rede ou timeout na OpenAI após {self.max_retries} tentativas: {net_err}")
                logger.warning("Falha de rede transitória (%s). Tentando novamente em %ss...", net_err, backoff)
                time.sleep(backoff)
                backoff *= 2.0
