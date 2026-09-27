"""Cálculos financeiros com aritmética decimal precisa e conversão cambial."""

from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Dict, Optional, Tuple

DECIMAL_ZERO = Decimal("0.000000")


def to_decimal(val: Any) -> Optional[Decimal]:
    """Converte valores variados para Decimal com segurança."""
    if val is None or val == "":
        return None
    try:
        return Decimal(str(val))
    except Exception:
        return None


def calculate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    pricing_prompt: Optional[str],
    pricing_completion: Optional[str],
    pricing_unit: str = "per_1m_tokens",
    cache_read_tokens: int = 0,
    pricing_cache_read: Optional[str] = None,
    reasoning_tokens: int = 0,
    pricing_reasoning: Optional[str] = None,
) -> Tuple[Optional[Decimal], bool]:
    """Calcula o custo em dólares usando aritmética decimal exata.
    
    Retorna uma tupla (custo_decimal, preco_conhecido).
    Se o preço for desconhecido (None), retorna (None, False).
    """
    if pricing_prompt is None or pricing_completion is None:
        return None, False

    try:
        p_in = Decimal(str(pricing_prompt))
        p_out = Decimal(str(pricing_completion))
    except Exception:
        return None, False

    # Fator de conversão da unidade para custo por token
    if pricing_unit == "per_1m_tokens":
        divisor = Decimal("1000000")
    elif pricing_unit == "per_1k_tokens":
        divisor = Decimal("1000")
    elif pricing_unit == "per_token":
        divisor = Decimal("1")
    else:
        divisor = Decimal("1000000")

    in_rate = p_in / divisor
    out_rate = p_out / divisor

    cost = (Decimal(input_tokens) * in_rate) + (Decimal(output_tokens) * out_rate)

    # Custo adicional de cache se aplicável
    if cache_read_tokens > 0 and pricing_cache_read:
        try:
            c_rate = Decimal(str(pricing_cache_read)) / divisor
            cost += Decimal(cache_read_tokens) * c_rate
        except Exception:
            pass

    # Custo de tokens de raciocínio (o1/o3/DeepSeek R1 normalmente usam taxa de saída)
    if reasoning_tokens > 0:
        if pricing_reasoning:
            try:
                r_rate = Decimal(str(pricing_reasoning)) / divisor
                cost += Decimal(reasoning_tokens) * r_rate
            except Exception:
                pass

    return cost.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP), True


def estimate_pre_flight_cost(
    prompt_chars: int,
    expected_output_tokens: int,
    pricing_prompt: Optional[str],
    pricing_completion: Optional[str],
    pricing_unit: str = "per_1m_tokens",
    is_free: bool = False,
) -> Dict[str, Any]:
    """Estima tokens e custo prévio antes da chamada de rede."""
    if is_free:
        return {
            "estimated_input_tokens": max(1, int(prompt_chars / 3.8)),
            "estimated_output_tokens": expected_output_tokens,
            "estimated_cost_usd": Decimal("0.000000"),
            "is_known_price": True,
            "formatted_usd": "$0.0000 (Gratuito)",
        }

    # Para textos em língua portuguesa, a taxa média é aproximadamente 3.8 caracteres por token
    est_input_tokens = max(1, int(prompt_chars / 3.8))
    cost_dec, is_known = calculate_cost_usd(
        input_tokens=est_input_tokens,
        output_tokens=expected_output_tokens,
        pricing_prompt=pricing_prompt,
        pricing_completion=pricing_completion,
        pricing_unit=pricing_unit,
    )

    formatted = f"${cost_dec:.6f} USD" if is_known and cost_dec is not None else "Preço Desconhecido"

    return {
        "estimated_input_tokens": est_input_tokens,
        "estimated_output_tokens": expected_output_tokens,
        "estimated_cost_usd": cost_dec,
        "is_known_price": is_known,
        "formatted_usd": formatted,
    }


def convert_usd_to_brl(
    cost_usd: Optional[Decimal],
    exchange_rate: str = "5.50",
    exchange_date: str = "2026-09-27",
) -> Tuple[Optional[Decimal], str]:
    """Converte valor de USD para BRL registrando a cotação e data aplicada."""
    if cost_usd is None:
        return None, "Cotação: Não aplicável"

    try:
        rate = Decimal(str(exchange_rate))
        cost_brl = (cost_usd * rate).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        label = f"R$ {cost_brl:.4f} (Cotação R$ {rate:.2f} de {exchange_date})"
        return cost_brl, label
    except Exception:
        return None, "Erro na conversão cambial"
