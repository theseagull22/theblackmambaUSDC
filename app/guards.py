from __future__ import annotations


def min_allowed_sell_price(avg_cost: float, min_profit_floor: float) -> float:
    return avg_cost + min_profit_floor


def validate_sell_not_below_cost_floor(*, avg_cost: float, min_profit_floor: float, proposed_price: float) -> None:
    floor_price = min_allowed_sell_price(avg_cost, min_profit_floor)
    if proposed_price < floor_price:
        raise ValueError(
            f"Rule Zero violation: proposed sell {proposed_price:.8f} is below floor {floor_price:.8f}"
        )
