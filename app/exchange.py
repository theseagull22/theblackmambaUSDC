from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TopOfBook:
    best_bid: float
    best_ask: float

    @property
    def mid(self) -> float:
        return (self.best_bid + self.best_ask) / 2.0


@dataclass
class OrderSnapshot:
    order_id: str
    side: str
    price: float
    qty: float
    status: str


class BybitSpotClient:
    def __init__(self, *, api_key: str, api_secret: str, testnet: bool, demo: bool):
        try:
            from pybit.unified_trading import HTTP
        except ImportError as exc:
            raise RuntimeError("pybit is not installed. Install requirements first.") from exc

        self.session = HTTP(
            testnet=testnet,
            demo=demo,
            api_key=api_key,
            api_secret=api_secret,
        )

    def get_top_of_book(self, symbol: str) -> TopOfBook:
        response = self.session.get_tickers(category="spot", symbol=symbol)
        items = (response or {}).get("result", {}).get("list", [])
        if not items:
            raise RuntimeError(f"No ticker data returned for {symbol}")
        item = items[0]
        best_bid = float(item["bid1Price"])
        best_ask = float(item["ask1Price"])
        return TopOfBook(best_bid=best_bid, best_ask=best_ask)

    def get_open_orders(self, symbol: str) -> Dict[str, OrderSnapshot]:
        response = self.session.get_open_orders(category="spot", symbol=symbol)
        items = (response or {}).get("result", {}).get("list", [])
        out: Dict[str, OrderSnapshot] = {}
        for item in items:
            order_id = item.get("orderId")
            if not order_id:
                continue
            out[order_id] = OrderSnapshot(
                order_id=order_id,
                side=item.get("side", ""),
                price=float(item.get("price") or 0.0),
                qty=float(item.get("qty") or 0.0),
                status=item.get("orderStatus", "Unknown"),
            )
        return out

    def get_order_history(self, *, symbol: str, order_id: str) -> Optional[OrderSnapshot]:
        response = self.session.get_order_history(category="spot", symbol=symbol, orderId=order_id, limit=20)
        items = (response or {}).get("result", {}).get("list", [])
        for item in items:
            if item.get("orderId") == order_id:
                return OrderSnapshot(
                    order_id=order_id,
                    side=item.get("side", ""),
                    price=float(item.get("avgPrice") or item.get("price") or 0.0),
                    qty=float(item.get("cumExecQty") or item.get("qty") or 0.0),
                    status=item.get("orderStatus", "Unknown"),
                )
        return None

    def get_wallet_balances(self, coin: Optional[str] = None) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"accountType": "UNIFIED"}
        if coin:
            kwargs["coin"] = coin
        return self.session.get_wallet_balance(**kwargs)

    def place_limit_post_only(self, *, symbol: str, side: str, qty: str, price: str) -> Dict[str, Any]:
        return self.session.place_order(
            category="spot",
            symbol=symbol,
            side=side,
            orderType="Limit",
            qty=qty,
            price=price,
            timeInForce="PostOnly",
        )

    def cancel_order(self, *, symbol: str, order_id: str) -> Dict[str, Any]:
        return self.session.cancel_order(category="spot", symbol=symbol, orderId=order_id)
