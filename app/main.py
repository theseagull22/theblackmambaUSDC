from __future__ import annotations

import math
import time
from typing import Optional

from app.config import Settings
from app.exchange import BybitSpotClient
from app.logger import setup_logger
from app.state import BotState
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

    def _round_price(self, price: float) -> float:
        # Good enough for starter work on a stable/stable spot pair.
        return round(price, 4)

    def _needs_reprice(self, current: Optional[float], desired: Optional[float]) -> bool:
        if desired is None:
            return False
        if current is None:
            return True
        return math.fabs(current - desired) >= self.settings.price_reprice_threshold

    def _paper_quote_bid(self, desired_price: float) -> None:
        desired_price = self._round_price(desired_price)
        if self._needs_reprice(self.state.active_bid_price, desired_price):
            self.log.info(
                "PAPER | would quote BUY %s %s at %.4f",
                self.settings.order_size,
                self.settings.symbol,
                desired_price,
            )
            self.state.active_bid_price = desired_price
            self.state.active_bid_order_id = "PAPER_BID"
            self.state.active_ask_price = None
            self.state.active_ask_order_id = None

    def _paper_quote_ask(self, desired_price: float) -> None:
        desired_price = self._round_price(desired_price)
        if self._needs_reprice(self.state.active_ask_price, desired_price):
            self.log.info(
                "PAPER | would quote SELL %s %s at %.4f",
                self.state.inventory_qty or self.settings.order_size,
                self.settings.symbol,
                desired_price,
            )
            self.state.active_ask_price = desired_price
            self.state.active_ask_order_id = "PAPER_ASK"
            self.state.active_bid_price = None
            self.state.active_bid_order_id = None

    def _live_quote_bid(self, desired_price: float) -> None:
        desired_price = self._round_price(desired_price)
        if not self._needs_reprice(self.state.active_bid_price, desired_price):
            return
        self.log.info("LIVE | bid reprice requested at %.4f", desired_price)
        # Starter live behavior: quote only if there is no active live order recorded.
        if self.state.active_bid_order_id is None:
            result = self.client.place_limit_post_only(
                symbol=self.settings.symbol,
                side="Buy",
                qty=str(self.settings.order_size),
                price=f"{desired_price:.4f}",
            )
            order_id = ((result or {}).get("result") or {}).get("orderId")
            self.state.active_bid_order_id = order_id
            self.state.active_bid_price = desired_price
            self.state.active_ask_order_id = None
            self.state.active_ask_price = None
            self.log.info("LIVE | placed bid order_id=%s price=%.4f", order_id, desired_price)
        else:
            self.log.info("LIVE | active bid already tracked; manual amend/cancel logic is next step")

    def _live_quote_ask(self, desired_price: float) -> None:
        desired_price = self._round_price(desired_price)
        if not self._needs_reprice(self.state.active_ask_price, desired_price):
            return
        self.log.info("LIVE | ask reprice requested at %.4f", desired_price)
        if self.state.active_ask_order_id is None:
            qty = self.state.inventory_qty or self.settings.order_size
            result = self.client.place_limit_post_only(
                symbol=self.settings.symbol,
                side="Sell",
                qty=str(qty),
                price=f"{desired_price:.4f}",
            )
            order_id = ((result or {}).get("result") or {}).get("orderId")
            self.state.active_ask_order_id = order_id
            self.state.active_ask_price = desired_price
            self.state.active_bid_order_id = None
            self.state.active_bid_price = None
            self.log.info("LIVE | placed ask order_id=%s price=%.4f", order_id, desired_price)
        else:
            self.log.info("LIVE | active ask already tracked; manual amend/cancel logic is next step")

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
                fair = self.strategy.fair_value(best_bid=tob.best_bid, best_ask=tob.best_ask)

                self.state.last_best_bid = tob.best_bid
                self.state.last_best_ask = tob.best_ask
                self.state.last_fair_value = fair

                decision = self.strategy.decide(
                    state=self.state,
                    best_bid=tob.best_bid,
                    best_ask=tob.best_ask,
                )

                self.log.info(
                    "Tick | mode=%s | bid=%.4f | ask=%.4f | fair=%.4f | reason=%s",
                    self.state.mode,
                    tob.best_bid,
                    tob.best_ask,
                    fair,
                    decision.reason,
                )

                if self.settings.paper_mode:
                    if decision.desired_bid_price is not None:
                        self._paper_quote_bid(decision.desired_bid_price)
                    if decision.desired_ask_price is not None:
                        self._paper_quote_ask(decision.desired_ask_price)
                else:
                    if decision.desired_bid_price is not None:
                        self._live_quote_bid(decision.desired_bid_price)
                    if decision.desired_ask_price is not None:
                        self._live_quote_ask(decision.desired_ask_price)

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
