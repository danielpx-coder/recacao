"""Testes automatizados com respostas simuladas para os adaptadores OpenAI, Anthropic e OpenRouter."""

import json
import httpx
import pytest
from danaurium.providers.openai_provider import OpenAIProvider
from danaurium.providers.anthropic_provider import AnthropicProvider
from danaurium.providers.openrouter_provider import OpenRouterProvider
from danaurium.providers.custom_openai import CustomOpenAIProvider
from danaurium.providers.base import (
    GenerationRequest, normalize_url, AuthenticationError,
    QuotaExceededError, RateLimitError
)

_ORIG_CLIENT = httpx.Client


def set_mock_transport(monkeypatch, handler):
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(httpx, "Client", lambda **kwargs: _ORIG_CLIENT(transport=transport, **kwargs))


def test_url_normalization():
    assert normalize_url("https://api.openai.com/v1", "/models") == "https://api.openai.com/v1/models"
    assert normalize_url("https://api.openai.com/v1/", "models") == "https://api.openai.com/v1/models"
    # Evita duplicação de /v1
    assert normalize_url("https://api.openai.com/v1", "v1/models") == "https://api.openai.com/v1/models"
    assert normalize_url("https://api.openai.com/v1/", "/v1/models") == "https://api.openai.com/v1/models"


def test_openai_catalog_and_headers(monkeypatch):
    captured_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if request.url.path.endswith("/models"):
            data = {
                "data": [
                    {"id": "gpt-4o", "owned_by": "openai"},
                    {"id": "gpt-4o-mini", "owned_by": "openai"},
                    {"id": "text-embedding-3-small", "owned_by": "openai"},  # deve ser filtrado
                ]
            }
            return httpx.Response(200, json=data)
        return httpx.Response(404)

    set_mock_transport(monkeypatch, mock_handler)

    conn_data = {
        "id": "c_openai",
        "name": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "catalog_path": "/models",
        "generation_path": "/chat/completions",
    }
    provider = OpenAIProvider(conn_data, api_key="sk-test-key-openai")

    catalog = provider.fetch_catalog()
    assert len(catalog) == 2  # O embedding foi filtrado
    assert catalog[0].model_id in ("gpt-4o", "gpt-4o-mini")

    req = captured_requests[0]
    assert req.headers["authorization"] == "Bearer sk-test-key-openai"
    assert req.url == "https://api.openai.com/v1/models"


def test_openai_streaming_generation(monkeypatch):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        # Simular SSE stream da OpenAI Chat Completions
        sse_lines = [
            'data: {"choices": [{"delta": {"content": "O Ministério da Educação"}}]}\n\n',
            'data: {"choices": [{"delta": {"content": " anunciou novas diretrizes."}}]}\n\n',
            'data: {"choices": [{"finish_reason": "stop"}], "usage": {"prompt_tokens": 120, "completion_tokens": 15}}\n\n',
            'data: [DONE]\n\n',
        ]
        return httpx.Response(200, content="".join(sse_lines).encode("utf-8"), headers={"content-type": "text/event-stream"})

    set_mock_transport(monkeypatch, mock_handler)

    conn_data = {
        "id": "c_openai",
        "base_url": "https://api.openai.com/v1",
        "generation_path": "/chat/completions",
    }
    provider = OpenAIProvider(conn_data, api_key="sk-test")

    req = GenerationRequest(
        model_id="gpt-4o",
        user_prompt="Escreva a abertura da matéria.",
        system_prompt="Você é um jornalista.",
    )

    chunks = list(provider.generate_stream(req))
    full_text = "".join(c.text for c in chunks)
    assert full_text == "O Ministério da Educação anunciou novas diretrizes."

    last_chunk = chunks[-1]
    assert last_chunk.usage is not None
    assert last_chunk.usage.input_tokens == 120
    assert last_chunk.usage.output_tokens == 15


def test_openai_error_handling_401_429(monkeypatch):
    def mock_401(request: httpx.Request):
        return httpx.Response(401, json={"error": {"message": "Invalid API key."}})

    set_mock_transport(monkeypatch, mock_401)

    provider = OpenAIProvider({"base_url": "https://api.openai.com/v1"}, api_key="sk-inv")
    with pytest.raises(AuthenticationError):
        provider.fetch_catalog()


def test_anthropic_catalog_pagination_and_headers(monkeypatch):
    captured_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        after_id = request.url.params.get("after_id")
        if not after_id:
            # Primeira página
            return httpx.Response(200, json={
                "data": [{"id": "claude-3-5-sonnet-20241022", "display_name": "Claude 3.5 Sonnet"}],
                "has_more": True,
                "last_id": "model_page_1_last",
            })
        else:
            # Segunda página final
            return httpx.Response(200, json={
                "data": [{"id": "claude-3-haiku-20240307", "display_name": "Claude 3 Haiku"}],
                "has_more": False,
                "last_id": "model_page_2_last",
            })

    set_mock_transport(monkeypatch, mock_handler)

    conn_data = {
        "id": "c_anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "catalog_path": "/models",
    }
    provider = AnthropicProvider(conn_data, api_key="sk-ant-test-key")

    catalog = provider.fetch_catalog()
    assert len(catalog) == 2
    assert len(captured_requests) == 2  # Validou paginação em 2 chamadas

    # Validar cabeçalhos oficiais da Anthropic
    req1 = captured_requests[0]
    assert req1.headers["x-api-key"] == "sk-ant-test-key"
    assert req1.headers["anthropic-version"] == "2023-06-01"
    assert "Bearer" not in req1.headers.get("authorization", "")


def test_anthropic_streaming_messages_and_tokens(monkeypatch):
    captured_body = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_body
        captured_body = json.loads(request.content.decode("utf-8"))

        sse_events = [
            'data: {"type": "message_start", "message": {"usage": {"input_tokens": 150, "cache_read_input_tokens": 30}}}\n\n',
            'data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Texto inicial claude."}}\n\n',
            'data: {"type": "message_delta", "delta": {"stop_reason": "end_turn"}, "usage": {"output_tokens": 40}}\n\n',
            'data: {"type": "message_stop"}\n\n',
        ]
        return httpx.Response(200, content="".join(sse_events).encode("utf-8"), headers={"content-type": "text/event-stream"})

    set_mock_transport(monkeypatch, mock_handler)

    conn_data = {"base_url": "https://api.anthropic.com/v1", "generation_path": "/messages"}
    provider = AnthropicProvider(conn_data, api_key="sk-ant-test")

    req = GenerationRequest(
        model_id="claude-3-5-sonnet-20241022",
        user_prompt="Instrução do usuário",
        system_prompt="Diretriz de sistema de topo",
    )

    chunks = list(provider.generate_stream(req))
    assert "".join(c.text for c in chunks) == "Texto inicial claude."

    # Verificar que o prompt de sistema foi enviado no campo de 1º nível 'system'
    assert captured_body["system"] == "Diretriz de sistema de topo"
    assert captured_body["messages"][0]["role"] == "user"

    # Verificar tokens capturados
    last_chunk = chunks[-1]
    assert last_chunk.usage.input_tokens == 150
    assert last_chunk.usage.cache_read_tokens == 30
    assert last_chunk.usage.output_tokens == 40


def test_openrouter_catalog_pricing_and_free_router(monkeypatch):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        models_data = {
            "data": [
                {
                    "id": "meta-llama/llama-3.3-70b-instruct:free",
                    "name": "Llama 3.3 70B (free)",
                    "pricing": {"prompt": "0", "completion": "0"},
                    "context_length": 131072,
                },
                {
                    "id": "anthropic/claude-3.5-sonnet",
                    "name": "Claude 3.5 Sonnet",
                    "pricing": {"prompt": "0.000003", "completion": "0.000015"},  # $3/1M in, $15/1M out
                    "context_length": 200000,
                },
            ]
        }
        return httpx.Response(200, json=models_data)

    set_mock_transport(monkeypatch, mock_handler)

    conn_data = {"base_url": "https://openrouter.ai/api/v1", "catalog_path": "/models"}
    provider = OpenRouterProvider(conn_data, api_key="sk-or-v1-test")

    catalog = provider.fetch_catalog()

    # Deve conter os 2 modelos da API + a rota especial openrouter/free
    ids = [m.model_id for m in catalog]
    assert "openrouter/free" in ids
    assert "meta-llama/llama-3.3-70b-instruct:free" in ids

    # Validar conversão de preço por token para preço por 1 milhão
    claude_m = next(m for m in catalog if m.model_id == "anthropic/claude-3.5-sonnet")
    assert claude_m.pricing_prompt == "3.000000"
    assert claude_m.pricing_completion == "15.000000"
    assert claude_m.is_free is False

    llama_free = next(m for m in catalog if m.model_id == "meta-llama/llama-3.3-70b-instruct:free")
    assert llama_free.is_free is True


def test_streaming_cancellation():
    class DummyProvider(OpenAIProvider):
        def generate_stream(self, request, cancel_check=None):
            for i in range(10):
                if cancel_check and cancel_check():
                    return
                yield i

    provider = DummyProvider({"base_url": "http://dummy"}, api_key="test")
    cancelled = False

    def check_cancel():
        return cancelled

    received = []
    for val in provider.generate_stream(GenerationRequest(model_id="test", user_prompt=""), cancel_check=check_cancel):
        received.append(val)
        if val == 2:
            cancelled = True

    assert received == [0, 1, 2]  # Interrompeu imediatamente após o cancelamento
