from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    bybit_api_key: str
    bybit_api_secret: str
    bybit_testnet: bool
    bybit_demo: bool
    symbol: str
    category: str
    paper_mode: bool
    order_size: float
    entry_offset: float
    exit_offset: float
    min_profit_floor: float
    price_reprice_threshold: float
    bid_ttl_sec: float
    ask_ttl_sec: float
    allow_ask_reprice_down: bool
    paper_fill_on_touch: bool
    loop_interval_sec: float
    state_file: Path
    log_level: str

    @staticmethod
    def _get_bool(name: str, default: bool) -> bool:
        raw = os.getenv(name, str(default)).strip().lower()
        return raw in {"1", "true", "yes", "y", "on"}

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            bybit_api_key=os.getenv("BYBIT_API_KEY", "").strip(),
            bybit_api_secret=os.getenv("BYBIT_API_SECRET", "").strip(),
            bybit_testnet=cls._get_bool("BYBIT_TESTNET", False),
            bybit_demo=cls._get_bool("BYBIT_DEMO", False),
            symbol=os.getenv("SYMBOL", "USDCUSDT").strip() or "USDCUSDT",
            category=os.getenv("CATEGORY", "spot").strip() or "spot",
            paper_mode=cls._get_bool("PAPER_MODE", True),
            order_size=float(os.getenv("ORDER_SIZE", "1000")),
            entry_offset=float(os.getenv("ENTRY_OFFSET", "0.0001")),
            exit_offset=float(os.getenv("EXIT_OFFSET", "0.0001")),
            min_profit_floor=float(os.getenv("MIN_PROFIT_FLOOR", "0.0001")),
            price_reprice_threshold=float(os.getenv("PRICE_REPRICE_THRESHOLD", "0.0001")),
            bid_ttl_sec=float(os.getenv("BID_TTL_SEC", "30")),
            ask_ttl_sec=float(os.getenv("ASK_TTL_SEC", "120")),
            allow_ask_reprice_down=cls._get_bool("ALLOW_ASK_REPRICE_DOWN", False),
            paper_fill_on_touch=cls._get_bool("PAPER_FILL_ON_TOUCH", True),
            loop_interval_sec=float(os.getenv("LOOP_INTERVAL_SEC", "2")),
            state_file=Path(os.getenv("STATE_FILE", "state.json")).expanduser(),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )

    def validate(self) -> None:
        if self.category != "spot":
            raise ValueError("This version is intended for Bybit Spot only.")
        if self.order_size <= 0:
            raise ValueError("ORDER_SIZE must be > 0")
        if self.min_profit_floor <= 0:
            raise ValueError("MIN_PROFIT_FLOOR must be > 0")
        if self.loop_interval_sec <= 0:
            raise ValueError("LOOP_INTERVAL_SEC must be > 0")
        if self.bid_ttl_sec <= 0:
            raise ValueError("BID_TTL_SEC must be > 0")
        if self.ask_ttl_sec <= 0:
            raise ValueError("ASK_TTL_SEC must be > 0")
