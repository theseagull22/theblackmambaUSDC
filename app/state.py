from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class BotState:
    mode: str = "FLAT_USDT"
    symbol: str = "USDCUSDT"
    avg_cost: Optional[float] = None
    inventory_qty: float = 0.0
    active_bid_order_id: Optional[str] = None
    active_ask_order_id: Optional[str] = None
    active_bid_price: Optional[float] = None
    active_ask_price: Optional[float] = None
    last_fill_price: Optional[float] = None
    last_fill_at: Optional[str] = None
    last_fair_value: Optional[float] = None
    last_best_bid: Optional[float] = None
    last_best_ask: Optional[float] = None
    updated_at: str = field(default_factory=utc_now_iso)

    def touch(self) -> None:
        self.updated_at = utc_now_iso()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "BotState":
        return cls(**payload)
