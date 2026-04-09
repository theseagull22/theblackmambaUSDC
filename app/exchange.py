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

    def get_wallet_balances(self, coin: Optional[str] = None) -> Dict[str, Any]:
        kwargs: Dict[str, Any] = {"accountType": "UNIFIED"}
        if coin:
            kwargs["coin"] = coin
        return self.session.get_wallet_balance(**kwargs)

    def get_open_orders(self, symbol: str) -> Dict[str, Any]:
        return self.session.get_open_orders(category="spot", symbol=symbol)

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

    def cancel_order(self, *, symbol: str, order_id: Optional[str] = None, order_link_id: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"category": "spot", "symbol": symbol}
        if order_id:
            payload["orderId"] = order_id
        if order_link_id:
            payload["orderLinkId"] = order_link_id
        return self.session.cancel_order(**payload)
