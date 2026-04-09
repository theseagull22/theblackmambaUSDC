from __future__ import annotations

import logging


def setup_logger(level: str) -> logging.Logger:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    return logging.getLogger("theblackmambaPEG")
