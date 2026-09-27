"""Gerenciamento de orçamento, tetos diário/mensal e reserva de custo para chamadas concorrentes."""

import threading
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, Optional, Tuple
from danaurium.persistence.repository import Repository, repo

logger = logging.getLogger("danaurium.budget.manager")


class BudgetExceededError(Exception):
    """Lançada quando a operação ultrapassa os limites de orçamento configurados."""
    pass


class BudgetManager:
    """Controla tetos de gastos diários, mensais e por projeto com reserva para concorrência."""

    def __init__(self, repository: Optional[Repository] = None):
        self.repo = repository or repo
        self._lock = threading.Lock()
        # Mapeia reservation_id -> (project_id, estimated_cost_usd)
        self._active_reservations: Dict[str, Tuple[Optional[str], Decimal]] = {}

    def get_settings(self) -> Dict[str, Any]:
        return self.repo.get_budget_settings()

    def update_settings(self, settings_data: Dict[str, Any]):
        self.repo.update_budget_settings(settings_data)

    def get_current_spend(self, project_id: Optional[str] = None) -> Dict[str, Decimal]:
        """Calcula o gasto acumulado de hoje, do mês corrente e do projeto informado."""
        today_str = date.today().isoformat()
        current_month_prefix = datetime.utcnow().strftime("%Y-%m")

        logs = self.repo.get_usage_logs()

        daily_spend = Decimal("0.000000")
        monthly_spend = Decimal("0.000000")
        project_spend = Decimal("0.000000")

        for l in logs:
            cost_str = l.get("cost_calculated") or "0"
            try:
                c_dec = Decimal(cost_str)
            except Exception:
                continue

            created = l.get("created_at", "")
            if created.startswith(today_str):
                daily_spend += c_dec
            if created.startswith(current_month_prefix):
                monthly_spend += c_dec
            if project_id and l.get("project_id") == project_id:
                project_spend += c_dec

        return {
            "daily_usd": daily_spend,
            "monthly_usd": monthly_spend,
            "project_usd": project_spend,
        }

    def reserve_budget(
        self,
        reservation_id: str,
        estimated_cost_usd: Optional[Decimal],
        project_id: Optional[str] = None,
        is_free: bool = False,
    ) -> Tuple[bool, str]:
        """Reserva orçamento antes de uma chamada assíncrona/concorrente.
        
        Bloqueia a requisição se os limites diário, mensal ou do projeto forem ultrapassados.
        """
        settings = self.get_settings()
        strict_free = bool(settings.get("strict_free_mode", False))
        strict_budget = bool(settings.get("strict_budget_mode", False))

        if strict_free and not is_free:
            return False, "Operação bloqueada: O modo 'Somente Gratuitos' está ativado globalmente."

        if is_free:
            return True, "Modelo gratuito aprovado sem impacto no orçamento financeiro."

        if estimated_cost_usd is None:
            if strict_budget:
                return False, "Operação bloqueada: Preço do modelo é desconhecido e o Modo de Orçamento Estrito está ativado."
            # Se não estiver em modo estrito, permite mas assume estimativa cautelosa mínima
            estimated_cost_usd = Decimal("0.005")

        with self._lock:
            # Somar gastos já consolidados
            current = self.get_current_spend(project_id)
            
            # Somar reservas ativas correntes em execução concorrente
            active_pending = sum(cost for _, cost in self._active_reservations.values())
            project_pending = sum(cost for pid, cost in self._active_reservations.values() if pid == project_id)

            daily_limit = Decimal(str(settings.get("daily_limit_usd", "10.00")))
            monthly_limit = Decimal(str(settings.get("monthly_limit_usd", "100.00")))
            proj_limit = Decimal(str(settings.get("project_limit_usd", "5.00")))

            projected_daily = current["daily_usd"] + active_pending + estimated_cost_usd
            projected_monthly = current["monthly_usd"] + active_pending + estimated_cost_usd

            if projected_daily > daily_limit:
                return False, f"Limite diário de ${daily_limit:.2f} USD excedido (previsto: ${projected_daily:.4f} USD)."

            if projected_monthly > monthly_limit:
                return False, f"Limite mensal de ${monthly_limit:.2f} USD excedido (previsto: ${projected_monthly:.4f} USD)."

            if project_id:
                projected_proj = current["project_usd"] + project_pending + estimated_cost_usd
                if projected_proj > proj_limit:
                    return False, f"Teto do projeto de ${proj_limit:.2f} USD excedido (previsto: ${projected_proj:.4f} USD)."

            # Registra reserva ativa vinculada ao projeto
            self._active_reservations[reservation_id] = (project_id, estimated_cost_usd)
            return True, f"Reserva de ${estimated_cost_usd:.6f} USD alocada com sucesso."

    def release_reservation(self, reservation_id: str):
        """Libera a reserva temporária após a conclusão da chamada ou em caso de erro."""
        with self._lock:
            self._active_reservations.pop(reservation_id, None)


# Instância global do gerenciador de orçamento
budget_manager = BudgetManager()
