"""Agregação e relatórios de consumo de tokens e custos para o painel de faturamento."""

from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional
from danaurium.persistence.repository import Repository, repo
from danaurium.catalog.pricing import convert_usd_to_brl


class UsageTracker:
    """Consolidador de métricas para o dashboard de consumo."""

    def __init__(self, repository: Optional[Repository] = None):
        self.repo = repository or repo

    def get_summary(
        self,
        period: str = "this_month",  # 'today', 'this_week', 'this_month', 'all'
        project_id: Optional[str] = None,
        connection_id: Optional[str] = None,
        model_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Gera sumário consolidado com distinção transparente de todas as métricas."""
        now = datetime.utcnow()
        start_date = None

        if period == "today":
            start_date = date.today().isoformat()
        elif period == "this_week":
            start_date = (date.today() - timedelta(days=date.today().weekday())).isoformat()
        elif period == "this_month":
            start_date = now.strftime("%Y-%m-01")

        logs = self.repo.get_usage_logs(
            start_date=start_date,
            project_id=project_id,
            connection_id=connection_id,
            model_id=model_id,
        )

        total_requests = len(logs)
        total_input_tokens = 0
        total_output_tokens = 0
        total_cache_tokens = 0
        total_reasoning_tokens = 0
        total_latency_ms = 0

        total_estimated_usd = Decimal("0.000000")
        total_calculated_usd = Decimal("0.000000")
        total_reported_usd = Decimal("0.000000")
        has_reported_costs = False

        budget_settings = self.repo.get_budget_settings()
        brl_rate = budget_settings.get("usd_to_brl_rate", "5.50")
        brl_date = budget_settings.get("usd_to_brl_date", "2026-09-27")

        for l in logs:
            total_input_tokens += l.get("tokens_input", 0)
            total_output_tokens += l.get("tokens_output", 0)
            total_cache_tokens += l.get("tokens_cache_read", 0) + l.get("tokens_cache_write", 0)
            total_reasoning_tokens += l.get("tokens_reasoning", 0)
            total_latency_ms += l.get("latency_ms", 0)

            try:
                total_estimated_usd += Decimal(l.get("pre_flight_estimate") or "0")
            except Exception:
                pass

            try:
                total_calculated_usd += Decimal(l.get("cost_calculated") or "0")
            except Exception:
                pass

            if l.get("cost_provider_reported"):
                try:
                    total_reported_usd += Decimal(str(l["cost_provider_reported"]))
                    has_reported_costs = True
                except Exception:
                    pass

        avg_latency = int(total_latency_ms / total_requests) if total_requests > 0 else 0

        # Conversão cambial
        calc_brl, brl_info = convert_usd_to_brl(total_calculated_usd, brl_rate, brl_date)

        return {
            "period": period,
            "total_requests": total_requests,
            "tokens": {
                "input": total_input_tokens,
                "output": total_output_tokens,
                "cache": total_cache_tokens,
                "reasoning": total_reasoning_tokens,
                "total": total_input_tokens + total_output_tokens,
            },
            "costs": {
                "pre_flight_estimate_usd": total_estimated_usd,
                "calculated_by_app_usd": total_calculated_usd,
                "provider_confirmed_usd": total_reported_usd if has_reported_costs else None,
                "calculated_by_app_brl": calc_brl,
                "brl_conversion_info": brl_info,
            },
            "average_latency_ms": avg_latency,
            "raw_logs": logs,
        }


# Instância global do rastreador de uso
usage_tracker = UsageTracker()
