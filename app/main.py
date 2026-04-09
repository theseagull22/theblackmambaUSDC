from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from typing import Optional

from app.config import Settings
from app.exchange import BybitSpotClient, OrderSnapshot
from app.logger import setup_logger
from app.state import BotState, MODE_FLAT, MODE_HOLDING
from app.storage import JsonStateStore
from app.strategy import PegStrategyV1


class BotApp:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.settings.validate()
        self.log = setup_logger(settings.log_level)
        self.store = JsonStateStore(settings.state_file)
        self.state = self.store.load()
        self.state.symbol = settings.symbol
        self.strategy = PegStrategyV1(
            entry_offset=settings.entry_offset,
            exit_offset=settings.exit_offset,
            min_profit_floor=settings.min_profit_floor,
        )
        self.client = BybitSpotClient(
            api_key=settings.bybit_api_key,
            api_secret=settings.bybit_api_secret,
            testnet=settings.bybit_testnet,
            demo=settings.bybit_demo,
        )

    @staticmethod
    def _round_price(price: float) -> float:
        return round(price, 4)

    @staticmethod
    def _now_ts() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_iso(ts: Optional[str]) -> Optional[datetime]:
        if not ts:
            return None
        return datetime.fromisoformat(ts)

    def _age_sec(self, ts: Optional[str]) -> Optional[float]:
        dt = self._parse_iso(ts)
        if dt is None:
            return None
        return (self._now_ts() - dt).total_seconds()

    def _price_changed_enough(self, current: Optional[float], desired: Optional[float]) -> bool:
        if desired is None:
            return False
        if current is None:
            return True
        return math.fabs(current - desired) >= self.settings.price_reprice_threshold

    def _bid_needs_reprice(self, desired_price: float) -> bool:
        age = self._age_sec(self.state.active_bid_created_at)
        return (
            self.state.active_bid_price is None
            or self._price_changed_enough(self.state.active_bid_price, desired_price)
            or (age is not None and age >= self.settings.bid_ttl_sec)
        )

    def _ask_needs_reprice(self, desired_price: float) -> bool:
        if self.state.active_ask_price is None:
            return True
        age = self._age_sec(self.state.active_ask_created_at)
        if age is not None and age >= self.settings.ask_ttl_sec:
            return True
        if desired_price > self.state.active_ask_price + self.settings.price_reprice_threshold:
            return True
        if self.settings.allow_ask_reprice_down and self._price_changed_enough(self.state.active_ask_price, desired_price):
            return True
        return False

    def _new_paper_order_id(self, side: str) -> str:
        return f"PAPER_{side}_{int(time.time() * 1000)}"

    def _place_paper_bid(self, desired_price: float) -> None:
        price = self._round_price(desired_price)
        self.state.mark_bid_placed(self._new_paper_order_id("BID"), price)
        self.log.info("PAPER | placed BUY %s %s at %.4f", self.settings.order_size, self.settings.symbol, price)

    def _place_paper_ask(self, desired_price: float) -> None:
        price = self._round_price(desired_price)
        self.state.mark_ask_placed(self._new_paper_order_id("ASK"), price)
        qty = self.state.inventory_qty or self.settings.order_size
        self.log.info("PAPER | placed SELL %s %s at %.4f", qty, self.settings.symbol, price)

    def _cancel_paper_bid(self, reason: str) -> None:
        if self.state.active_bid_order_id:
            self.log.info("PAPER | cancel BUY order_id=%s | reason=%s", self.state.active_bid_order_id, reason)
            self.state.clear_bid()

    def _cancel_paper_ask(self, reason: str) -> None:
        if self.state.active_ask_order_id:
            self.log.info("PAPER | cancel SELL order_id=%s | reason=%s", self.state.active_ask_order_id, reason)
            self.state.clear_ask()

    def _place_live_bid(self, desired_price: float) -> None:
        price = self._round_price(desired_price)
        result = self.client.place_limit_post_only(
            symbol=self.settings.symbol,
            side="Buy",
            qty=str(self.settings.order_size),
            price=f"{price:.4f}",
        )
        order_id = ((result or {}).get("result") or {}).get("orderId")
        if not order_id:
            raise RuntimeError(f"Bid placement returned no orderId: {result}")
        self.state.mark_bid_placed(order_id, price)
        self.log.info("LIVE | placed BUY order_id=%s price=%.4f", order_id, price)

    def _place_live_ask(self, desired_price: float) -> None:
        price = self._round_price(desired_price)
        qty = self.state.inventory_qty or self.settings.order_size
        result = self.client.place_limit_post_only(
            symbol=self.settings.symbol,
            side="Sell",
            qty=str(qty),
            price=f"{price:.4f}",
        )
        order_id = ((result or {}).get("result") or {}).get("orderId")
        if not order_id:
            raise RuntimeError(f"Ask placement returned no orderId: {result}")
        self.state.mark_ask_placed(order_id, price)
        self.log.info("LIVE | placed SELL order_id=%s price=%.4f", order_id, price)

    def _cancel_live_bid(self, reason: str) -> None:
        if self.state.active_bid_order_id:
            self.client.cancel_order(symbol=self.settings.symbol, order_id=self.state.active_bid_order_id)
            self.log.info("LIVE | cancel BUY order_id=%s | reason=%s", self.state.active_bid_order_id, reason)
            self.state.clear_bid()

    def _cancel_live_ask(self, reason: str) -> None:
        if self.state.active_ask_order_id:
            self.client.cancel_order(symbol=self.settings.symbol, order_id=self.state.active_ask_order_id)
            self.log.info("LIVE | cancel SELL order_id=%s | reason=%s", self.state.active_ask_order_id, reason)
            self.state.clear_ask()

    def _mark_bid_fill(self, *, fill_price: float, qty: float, source: str) -> None:
        self.state.mark_bid_fill(price=fill_price, qty=qty)
        self.log.info(
            "%s | BUY fill | price=%.4f | qty=%s | mode=%s",
            source,
            fill_price,
            qty,
            self.state.mode,
        )

    def _mark_ask_fill(self, *, fill_price: float, source: str) -> None:
        qty = self.state.inventory_qty
        self.state.mark_ask_fill(price=fill_price)
        self.log.info(
            "%s | SELL fill | price=%.4f | qty=%s | mode=%s",
            source,
            fill_price,
            qty,
            self.state.mode,
        )

    def _simulate_paper_fills(self) -> None:
        if not self.settings.paper_fill_on_touch:
            return
        if self.state.mode == MODE_FLAT and self.state.active_bid_price is not None and self.state.last_best_ask is not None:
            if self.state.last_best_ask <= self.state.active_bid_price:
                self._mark_bid_fill(
                    fill_price=self.state.active_bid_price,
                    qty=self.settings.order_size,
                    source="PAPER",
                )
                return
        if self.state.mode == MODE_HOLDING and self.state.active_ask_price is not None and self.state.last_best_bid is not None:
            if self.state.last_best_bid >= self.state.active_ask_price:
                self._mark_ask_fill(fill_price=self.state.active_ask_price, source="PAPER")

    def _apply_live_order_status(self, snapshot: OrderSnapshot, tracked_side: str) -> None:
        status = snapshot.status.lower()
        if tracked_side == "Buy":
            if status == "filled":
                fill_price = snapshot.price or (self.state.active_bid_price or 0.0)
                fill_qty = snapshot.qty or self.settings.order_size
                self._mark_bid_fill(fill_price=fill_price, qty=fill_qty, source="LIVE")
            elif status in {"cancelled", "rejected", "deactivated"}:
                self.log.info("LIVE | BUY order ended with status=%s", snapshot.status)
                self.state.clear_bid()
        elif tracked_side == "Sell":
            if status == "filled":
                fill_price = snapshot.price or (self.state.active_ask_price or 0.0)
                self._mark_ask_fill(fill_price=fill_price, source="LIVE")
            elif status in {"cancelled", "rejected", "deactivated"}:
                self.log.info("LIVE | SELL order ended with status=%s", snapshot.status)
                self.state.clear_ask()

    def _reconcile_live_orders(self) -> None:
        open_orders = self.client.get_open_orders(self.settings.symbol)

        if self.state.active_bid_order_id:
            open_bid = open_orders.get(self.state.active_bid_order_id)
            if open_bid is not None:
                self.state.active_bid_price = open_bid.price or self.state.active_bid_price
            else:
                history = self.client.get_order_history(symbol=self.settings.symbol, order_id=self.state.active_bid_order_id)
                if history is not None:
                    self._apply_live_order_status(history, "Buy")
                else:
                    self.log.info("LIVE | BUY order_id=%s missing in open/history; clearing local bid", self.state.active_bid_order_id)
                    self.state.clear_bid()

        if self.state.active_ask_order_id:
            open_ask = open_orders.get(self.state.active_ask_order_id)
            if open_ask is not None:
                self.state.active_ask_price = open_ask.price or self.state.active_ask_price
            else:
                history = self.client.get_order_history(symbol=self.settings.symbol, order_id=self.state.active_ask_order_id)
                if history is not None:
                    self._apply_live_order_status(history, "Sell")
                else:
                    self.log.info("LIVE | SELL order_id=%s missing in open/history; clearing local ask", self.state.active_ask_order_id)
                    self.state.clear_ask()

    def _manage_flat_mode(self, desired_bid_price: float) -> None:
        if self.state.active_ask_order_id:
            if self.settings.paper_mode:
                self._cancel_paper_ask("flat_mode_no_inventory")
            else:
                self._cancel_live_ask("flat_mode_no_inventory")

        if self.state.active_bid_order_id is None:
            if self.settings.paper_mode:
                self._place_paper_bid(desired_bid_price)
            else:
                self._place_live_bid(desired_bid_price)
            return

        if self._bid_needs_reprice(desired_bid_price):
            if self.settings.paper_mode:
                self._cancel_paper_bid("bid_reprice_or_ttl")
                self._place_paper_bid(desired_bid_price)
            else:
                self._cancel_live_bid("bid_reprice_or_ttl")
                self._place_live_bid(desired_bid_price)

    def _manage_holding_mode(self, desired_ask_price: float) -> None:
        if self.state.active_bid_order_id:
            if self.settings.paper_mode:
                self._cancel_paper_bid("holding_mode_no_new_buys")
            else:
                self._cancel_live_bid("holding_mode_no_new_buys")

        if self.state.active_ask_order_id is None:
            if self.settings.paper_mode:
                self._place_paper_ask(desired_ask_price)
            else:
                self._place_live_ask(desired_ask_price)
            return

        if self._ask_needs_reprice(desired_ask_price):
            if self.settings.paper_mode:
                self._cancel_paper_ask("ask_reprice_or_ttl")
                self._place_paper_ask(desired_ask_price)
            else:
                self._cancel_live_ask("ask_reprice_or_ttl")
                self._place_live_ask(desired_ask_price)

    def run_forever(self) -> None:
        self.log.info(
            "Starting bot | symbol=%s | paper_mode=%s | state_file=%s",
            self.settings.symbol,
            self.settings.paper_mode,
            self.settings.state_file,
        )
        while True:
            try:
                tob = self.client.get_top_of_book(self.settings.symbol)
                self.state.last_best_bid = tob.best_bid
                self.state.last_best_ask = tob.best_ask
                self.state.last_fair_value = self.strategy.fair_value(best_bid=tob.best_bid, best_ask=tob.best_ask)

                if self.settings.paper_mode:
                    self._simulate_paper_fills()
                else:
                    self._reconcile_live_orders()

                decision = self.strategy.decide(
                    state=self.state,
                    best_bid=tob.best_bid,
                    best_ask=tob.best_ask,
                )

                self.log.info(
                    "Tick | mode=%s | bid=%.4f | ask=%.4f | fair=%.4f | active_bid=%s@%s | active_ask=%s@%s | reason=%s",
                    self.state.mode,
                    tob.best_bid,
                    tob.best_ask,
                    self.state.last_fair_value,
                    self.state.active_bid_order_id,
                    self.state.active_bid_price,
                    self.state.active_ask_order_id,
                    self.state.active_ask_price,
                    decision.reason,
                )

                if self.state.mode == MODE_FLAT and decision.desired_bid_price is not None:
                    self._manage_flat_mode(decision.desired_bid_price)
                elif self.state.mode == MODE_HOLDING and decision.desired_ask_price is not None:
                    self._manage_holding_mode(decision.desired_ask_price)

                self.state.touch()
                self.store.save(self.state)
            except KeyboardInterrupt:
                self.log.info("Stopping bot by user request")
                break
            except Exception as exc:
                self.log.exception("Loop error: %s", exc)
            time.sleep(self.settings.loop_interval_sec)


def main() -> None:
    settings = Settings.from_env()
    app = BotApp(settings)
    app.run_forever()


if __name__ == "__main__":
    main()
