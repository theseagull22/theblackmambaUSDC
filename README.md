# theblackmambaPEG

A fast, practical starter bot for USDCUSDT on Bybit Spot.

## Rule Zero

The bot must never place a sell order below its average cost plus a positive floor.

That means the system can risk time, but it does not realize a trading loss by chasing price down.
Getting stuck in USDC is acceptable by design.

## Scope of this starter repo

This is **Sprint 1 + a thin Sprint 2 skeleton**:

- separate repo
- local-first development
- polling-based runner
- state persisted to JSON
- paper mode by default
- exchange layer for Bybit REST
- simple strategy skeleton
- guard rails, including Rule Zero
- ready to move later into Render Background Worker

It is intentionally narrow:

- one pair: `USDCUSDT`
- one venue: Bybit Spot
- one inventory mode: `FLAT_USDT` or `HOLDING_USDC`
- max one active bid and one active ask in design
- no averaging down in v1
- no market orders

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

### 1. Create and activate venv

```bash
python -m venv .venv
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create env file

```bash
cp .env.example .env
```

Fill in your Bybit API key and secret.

### 4. Run in paper mode

```bash
python -m app.main
```

By default the bot will:

- load or initialize state
- poll best bid / best ask
- compute fair value
- compute desired bid or ask
- log what it **would** do in paper mode
- persist state to `state.json`

## Suggested development path

### Stage A — local connectivity
- verify ticker read works
- verify balances read works
- verify open orders read works

### Stage B — manual order ops
- test one PostOnly buy
- cancel it
- test one PostOnly sell
- cancel it

### Stage C — paper loop
- let it run in paper mode
- inspect logs and `state.json`

### Stage D — tiny live test
- very small size
- confirm it never places a sell below cost floor

### Stage E — Render
Once local behavior is stable, deploy as a **Render Background Worker**.
Start command:

```bash
python -m app.main
```

## Important notes

- This starter version uses REST polling for simplicity.
- Websocket order and market streams can be added later.
- The strategy is intentionally conservative and narrow.
- If there is any ambiguity, the bot should prefer doing nothing.
