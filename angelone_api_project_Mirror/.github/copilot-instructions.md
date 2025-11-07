## Quick context

This repository is an Angel One trade mirroring project focused on NIFTY options/futures. Primary goal: detect trades from a "source" account and mirror them to a "mirror" account with safety checks.

Key entry points
- `main.py` — interactive MirroringController (start/stop/enable/disable/emergency/status)
- `live_trading_bot.py` / `paper_trading_bot.py` — standalone bots demonstrating live/paper strategies (useful for data shape examples)

Core components (files you should read first)
- `src/config/config_manager.py` — environment-driven settings and account credentials (env keys: SOURCE_*/MIRROR_* + CHECK_INTERVAL, DRY_RUN, MIRROR_ENABLED)
- `src/auth/auth_manager.py` — TOTP-based authentication using `SmartConnect` objects (per-account connection caching)
- `src/detection/trade_detector.py` — reads source tradebook, normalizes trades into trade dicts and persists processed trade_keys (SQLite)
- `src/mirror/mirror_engine.py` — places orders into mirror account; contains retry and price-tolerance logic (place_angel_one_order is a placeholder to implement)
- `src/safety/safety_manager.py` — project-specific safety gates (mirroring_enabled flag, emergency stop, market-hours check, price validation)
- `src/mirror/position_tracker.py` — holdings diffs used to detect exits
- `src/analytics/pnl_tracker.py` & `src/health/` — lightweight trackers used by strategy and controller

Important repo-specific patterns & conventions
- Env-driven config: ConfigManager loads `/root/config.env` and `../.env`; other scripts sometimes reference platform-specific paths (e.g. `D:/tax/config.env`). Prefer centralizing secrets in a local `.env` for development.
- Safe defaults: `dry_run` defaults to true and `mirror_enabled` defaults to false — code expects mirroring to be opt-in.
- Trade identity: `trade_key` is the unique id used across systems (constructed in `TradeDetector.parse_trade`). Any mirroring logic must use that key to avoid duplicates.
- Persistence: Detected trades are persisted to an SQLite DB at the path from `processed_trades_db` (default `data/processed_trades.db`). Tests and manual runs clear/inspect this table.
- Price tolerance: Mirror decision uses `price_tolerance` (fraction). MirrorEngine has a placeholder LTP call — implement `get_current_market_price()` and `get_symbol_token()` before enabling real orders.

Data shape examples
- Normalized trade dict (example from `trade_detector.parse_trade`):
  {
    'trade_key': '<timestamp>_<symbol>_<qty>',
    'symbol': 'NIFTY25NOV23400CE',
    'quantity': 75,
    'order_type': 'BUY'|'SELL',
    'product_type': 'INTRADAY',
    'order_price': 45.5,
    'exchange': 'NFO'
  }

Where to implement production changes
- `src/mirror/mirror_engine.py`:
  - implement `get_current_market_price()` using Angel One LTP API
  - implement `get_symbol_token()` (or use `auth` connection searchscrip)
  - implement real `place_angel_one_order()` (currently simulates success)
- `src/utils/candle_loader.py` is currently empty — if you need re-usable candle loading, add helpers here and reuse across bots.

Developer workflows (how to run & test)
- Local run (interactive controller):
  - Ensure env vars for `SOURCE_*` and `MIRROR_*` are set (or update `src/config/config_manager.py` paths)
  - Start interactive controller: `python main.py` — then use the textual commands (start/enable/status/stop/emergency)
- Standalone bots: run `python paper_trading_bot.py` or `python live_trading_bot.py` for example data shapes and behavior
- Tests: repository uses pytest — run `pytest -q` to execute unit tests in `tests/`

Safety checklist before enabling real mirroring
1. Implement real order placement and symbol-token mapping in `MirrorEngine`.
2. Verify authentication works for both accounts via `src/auth/auth_manager.py`.
3. Confirm `processed_trades_db` location is writable and empty for a clean test run.
4. Run in `dry_run=False` only after small-scale simulation; default `dry_run=True` is safer.

Notes for AI agents
- Prefer small, local edits: implement missing API calls in `MirrorEngine` and add unit tests for those methods.
- When creating tests, mock `SmartConnect` responses (authentication, tradeBook, placeOrder, searchscrip) so CI never hits real endpoints.
- The codebase uses direct file paths in some scripts — normalize `.env` usage and prefer `src/config/config_manager.py` for canonical settings.

If anything in this summary looks incorrect or you want deeper details (call flows, specific tests to add, or help implementing `place_angel_one_order`), tell me which part to expand and I'll update the file.
