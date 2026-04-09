from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


MODE_FLAT = "FLAT_USDT"
MODE_HOLDING = "HOLDING_USDC"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BotState:
    mode: str = MODE_FLAT
    symbol: str = "USDCUSDT"
    avg_cost: Optional[float] = None
    inventory_qty: float = 0.0
    active_bid_order_id: Optional[str] = None
    active_ask_order_id: Optional[str] = None
    active_bid_price: Optional[float] = None
    active_ask_price: Optional[float] = None
    active_bid_created_at: Optional[str] = None
    active_ask_created_at: Optional[str] = None
    last_fill_side: Optional[str] = None
    last_fill_price: Optional[float] = None
    last_fill_qty: Optional[float] = None
    last_fill_at: Optional[str] = None
    last_exit_price: Optional[float] = None
    last_exit_at: Optional[str] = None
    last_fair_value: Optional[float] = None
    last_best_bid: Optional[float] = None
    last_best_ask: Optional[float] = None
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def clear_bid(self) -> None:
        self.active_bid_order_id = None
        self.active_bid_price = None
        self.active_bid_created_at = None

    def clear_ask(self) -> None:
        self.active_ask_order_id = None
        self.active_ask_price = None
        self.active_ask_created_at = None

    def mark_bid_placed(self, order_id: str, price: float) -> None:
        self.active_bid_order_id = order_id
        self.active_bid_price = price
        self.active_bid_created_at = utc_now_iso()
        self.clear_ask()
        self.touch()

    def mark_ask_placed(self, order_id: str, price: float) -> None:
        self.active_ask_order_id = order_id
        self.active_ask_price = price
        self.active_ask_created_at = utc_now_iso()
        self.clear_bid()
        self.touch()

    def mark_bid_fill(self, *, price: float, qty: float) -> None:
        self.mode = MODE_HOLDING
        self.avg_cost = price
        self.inventory_qty = qty
        self.last_fill_side = "Buy"
        self.last_fill_price = price
        self.last_fill_qty = qty
        self.last_fill_at = utc_now_iso()
        self.clear_bid()
        self.touch()

    def mark_ask_fill(self, *, price: float) -> None:
        self.mode = MODE_FLAT
        self.last_exit_price = price
        self.last_exit_at = utc_now_iso()
        self.last_fill_side = "Sell"
        self.last_fill_price = price
        self.last_fill_qty = self.inventory_qty
        self.last_fill_at = utc_now_iso()
        self.avg_cost = None
        self.inventory_qty = 0.0
        self.clear_ask()
        self.touch()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BotState":
        return cls(**payload)
