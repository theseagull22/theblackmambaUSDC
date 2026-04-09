# theblackmambaUSDC

A fast, practical USDCUSDT starter bot for Bybit Spot.

## Rule Zero

The bot must never place a sell order below its average cost plus a positive profit floor.

That means this system can get stuck in USDC, but it must not realize a trading loss by chasing price down.
Time risk is accepted by design. Realized sell-below-cost is not.

## What is in this Sprint 2 package

This version goes beyond the first paper skeleton.

It now includes:

- JSON-persisted bot state
- separate `FLAT_USDT` and `HOLDING_USDC` modes
- active bid / active ask tracking
- paper fill simulation on touch
- live open-order reconciliation skeleton
- live recent-order-history fill detection skeleton
- bid reprice / bid TTL
- ask quoting with Rule Zero hard floor
- optional ask repricing down toggle, off by default

## Project layout

```text
.
├── README.md
├── requirements.txt
├── .env.example
└── app
    ├── __init__.py
    ├── config.py
    ├── exchange.py
    ├── guards.py
    ├── logger.py
    ├── main.py
    ├── state.py
    ├── storage.py
    └── strategy.py
```

## Quick start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m app.main
```

## Recommended startup mode

Keep this first:

```env
PAPER_MODE=true
```

Let it run locally and watch the logs.
The first thing to verify is not profit. It is behavior:

- it stays alive
- it tracks one active bid in `FLAT_USDT`
- after paper touch-fill it flips to `HOLDING_USDC`
- it quotes one ask only
- that ask is never below `avg_cost + MIN_PROFIT_FLOOR`
- after paper sell-fill it returns to `FLAT_USDT`

## Notes

- This is still intentionally narrow and conservative.
- It uses REST polling for simplicity.
- Websocket market/order streams can be added later.
- If there is ambiguity, the bot should prefer doing nothing.
