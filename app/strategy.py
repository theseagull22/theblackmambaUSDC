from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.guards import min_allowed_sell_price, validate_sell_not_below_cost_floor
from app.state import BotState, MODE_FLAT, MODE_HOLDING


@dataclass
class StrategyDecision:
    desired_bid_price: Optional[float] = None
    desired_ask_price: Optional[float] = None
    reason: str = ""


class PegStrategyV1:
    def __init__(self, *, entry_offset: float, exit_offset: float, min_profit_floor: float):
        self.entry_offset = entry_offset
        self.exit_offset = exit_offset
        self.min_profit_floor = min_profit_floor

    def fair_value(self, *, best_bid: float, best_ask: float) -> float:
        return (best_bid + best_ask) / 2.0

    def decide(self, *, state: BotState, best_bid: float, best_ask: float) -> StrategyDecision:
        fair = self.fair_value(best_bid=best_bid, best_ask=best_ask)

        if state.mode == MODE_FLAT:
            return StrategyDecision(
                desired_bid_price=fair - self.entry_offset,
                desired_ask_price=None,
                reason="flat_mode_quote_bid",
            )

        if state.mode == MODE_HOLDING:
            if state.avg_cost is None:
                raise ValueError("HOLDING_USDC state requires avg_cost")
            floor_price = min_allowed_sell_price(state.avg_cost, self.min_profit_floor)
            dynamic_price = fair + self.exit_offset
            proposed_ask = max(floor_price, dynamic_price)
            validate_sell_not_below_cost_floor(
                avg_cost=state.avg_cost,
                min_profit_floor=self.min_profit_floor,
                proposed_price=proposed_ask,
            )
            return StrategyDecision(
                desired_bid_price=None,
                desired_ask_price=proposed_ask,
                reason="holding_mode_quote_ask",
            )

        raise ValueError(f"Unknown bot mode: {state.mode}")
