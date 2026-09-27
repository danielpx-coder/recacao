"""Testes de orçamento financeiro, limites diários/mensais e reservas para chamadas concorrentes."""

from decimal import Decimal
from danaurium.budget.manager import BudgetManager


def test_budget_reservation_within_limits(isolated_app_environment):
    repo = isolated_app_environment["repo"]
    repo.update_budget_settings({
        "daily_limit_usd": "10.00",
        "monthly_limit_usd": "50.00",
        "project_limit_usd": "2.00",
        "strict_budget_mode": False,
        "strict_free_mode": False,
    })

    budget = BudgetManager(repository=repo)

    # 1. Reserva permitida
    allowed, msg = budget.reserve_budget(
        reservation_id="res_1",
        estimated_cost_usd=Decimal("0.50"),
        project_id="proj_1",
        is_free=False,
    )
    assert allowed is True

    # 2. Segunda reserva concorrente que estoura o teto do projeto ($0.50 + $1.80 = $2.30 > $2.00)
    allowed2, msg2 = budget.reserve_budget(
        reservation_id="res_2",
        estimated_cost_usd=Decimal("1.80"),
        project_id="proj_1",
        is_free=False,
    )
    assert allowed2 is False
    assert "Teto do projeto" in msg2

    # 3. Liberar primeira reserva e tentar novamente
    budget.release_reservation("res_1")
    allowed3, msg3 = budget.reserve_budget(
        reservation_id="res_3",
        estimated_cost_usd=Decimal("1.80"),
        project_id="proj_1",
        is_free=False,
    )
    assert allowed3 is True


def test_strict_budget_mode_blocks_unknown_prices(isolated_app_environment):
    repo = isolated_app_environment["repo"]
    repo.update_budget_settings({
        "strict_budget_mode": True,  # Ativado
    })

    budget = BudgetManager(repository=repo)

    allowed, msg = budget.reserve_budget(
        reservation_id="res_unknown",
        estimated_cost_usd=None,  # Preço desconhecido
        is_free=False,
    )
    assert allowed is False
    assert "desconhecido" in msg.lower()
