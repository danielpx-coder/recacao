"""Testes de precisão financeira decimal, conversões de unidade e validação do modo Somente Gratuitos."""

from decimal import Decimal
from danaurium.catalog.pricing import calculate_cost_usd, estimate_pre_flight_cost, convert_usd_to_brl
from danaurium.catalog.manager import CatalogManager


def test_decimal_cost_calculation_per_1m():
    # 2.000 tokens de entrada a $2.50/1M = $0.005000
    # 500 tokens de saída a $10.00/1M = $0.005000
    # Total esperado: $0.010000 USD
    cost, is_known = calculate_cost_usd(
        input_tokens=2000,
        output_tokens=500,
        pricing_prompt="2.50",
        pricing_completion="10.00",
        pricing_unit="per_1m_tokens",
    )
    assert is_known is True
    assert cost == Decimal("0.010000")


def test_decimal_cost_with_cache_and_reasoning():
    # Entrada: 1.000 tokens a $3.00/1M = $0.003000
    # Saída: 200 tokens a $15.00/1M = $0.003000
    # Cache Read: 500 tokens a $0.30/1M = $0.000150
    # Raciocínio: 100 tokens a $15.00/1M = $0.001500
    # Total: $0.007650
    cost, is_known = calculate_cost_usd(
        input_tokens=1000,
        output_tokens=200,
        pricing_prompt="3.00",
        pricing_completion="15.00",
        pricing_unit="per_1m_tokens",
        cache_read_tokens=500,
        pricing_cache_read="0.30",
        reasoning_tokens=100,
        pricing_reasoning="15.00",
    )
    assert is_known is True
    assert cost == Decimal("0.007650")


def test_unknown_price_returns_unknown():
    cost, is_known = calculate_cost_usd(
        input_tokens=500,
        output_tokens=200,
        pricing_prompt=None,  # Preço desconhecido
        pricing_completion="10.00",
    )
    assert is_known is False
    assert cost is None


def test_pricing_units_conversions():
    # Teste de unidade por token direto (ex: 0.000002)
    cost1, _ = calculate_cost_usd(
        input_tokens=1000,
        output_tokens=1000,
        pricing_prompt="0.000002",
        pricing_completion="0.000008",
        pricing_unit="per_token",
    )
    assert cost1 == Decimal("0.010000")

    # Teste de unidade por mil tokens (per_1k_tokens)
    cost2, _ = calculate_cost_usd(
        input_tokens=1000,
        output_tokens=1000,
        pricing_prompt="0.002",
        pricing_completion="0.008",
        pricing_unit="per_1k_tokens",
    )
    assert cost2 == Decimal("0.010000")


def test_usd_to_brl_conversion():
    cost_usd = Decimal("2.000000")
    cost_brl, info = convert_usd_to_brl(cost_usd, exchange_rate="5.50", exchange_date="2026-09-27")
    assert cost_brl == Decimal("11.0000")
    assert "2026-09-27" in info
    assert "5.50" in info


def test_strict_free_mode_validation():
    manager = CatalogManager()

    # 1. Modelo Explicitamente Gratuito -> APROVADO
    free_model = {
        "model_id": "meta-llama/llama-3.3-70b-instruct:free",
        "display_name": "Llama 3.3 Free",
        "is_free": True,
        "pricing_prompt": "0.000000",
        "pricing_completion": "0.000000",
    }
    ok, msg = manager.validate_for_free_mode(free_model)
    assert ok is True

    # 2. Rota openrouter/free -> APROVADO
    router_model = {
        "model_id": "openrouter/free",
        "display_name": "Free Router",
    }
    ok, msg = manager.validate_for_free_mode(router_model)
    assert ok is True

    # 3. Modelo Pago -> BLOQUEADO
    paid_model = {
        "model_id": "gpt-4o",
        "display_name": "GPT-4o",
        "is_free": False,
        "pricing_prompt": "2.50",
        "pricing_completion": "10.00",
    }
    ok, msg = manager.validate_for_free_mode(paid_model)
    assert ok is False
    assert "PAGO" in msg

    # 4. Modelo com Preço Desconhecido -> BLOQUEADO PELO MODO GRATUITO
    unknown_model = {
        "model_id": "custom-unknown",
        "display_name": "Custom Model",
        "is_free": False,
        "pricing_prompt": None,
        "pricing_completion": None,
    }
    ok, msg = manager.validate_for_free_mode(unknown_model)
    assert ok is False
    assert "DESCONHECIDO" in msg, "Preço ausente NÃO pode ser presumido como zero!"
