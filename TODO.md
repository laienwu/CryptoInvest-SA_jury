# TODO — Repo Cleanup

## Critical — Stale config at import (all pipeline modules)

Every module below calls `_cfg = load_config()` at module level, freezing config
at import time. Environment variable changes and TOML edits after import are
silently ignored. This is the same bug we fixed in `ingest_postgres.py`.

- [x] **ingest.py** (line 40): `_cfg = load_config()` → 6 module-level constants derived from it (`DEFAULT_SYMBOLS`, `BINANCE_API_BASE`, `RATE_LIMIT_DELAY`, `MAX_RETRIES`, `DEFAULT_INTERVAL`, `DEFAULT_PERIOD_DAYS`). Functions use these stale constants as default parameter values, making them doubly frozen.
- [x] **transform.py** (line 40): `_cfg = load_config()` → `DEFAULT_SYMBOLS`, `TRADING_DAYS_PER_YEAR`
- [x] **optimize.py** (line 38): `_cfg = load_config()` → `RISK_FREE_RATE`, `GRID_STEPS`
- [x] **backtest.py** (line 44): `_cfg = load_config()` → `RISK_FREE_RATE`
- [x] **ingest_sources.py** (line 38): `_cfg = load_config()` → `DATA_DIR`, `REFERENCE_DIR`, `SYMBOLS_METADATA_CSV`, `PORTFOLIO_CONFIG_JSON`. DataSource subclasses reference these stale paths.

**Fix pattern**: Either resolve config inside functions (like `load_db_config()` in ingest_postgres), or accept config via parameter injection. For pure functions (transform math), accept the value as a parameter; for orchestration functions, resolve at call time.

---

## Critical — Cross-module coupling to private functions

- [x] **backtest.py** (lines 28–39): Imports 6 private/internal names from optimize and transform: `_grid_search_max_sharpe`, `_try_scipy_optimization`, `_align_data_by_date`, `calculate_log_returns`, `calculate_mean_returns`, `calculate_covariance_matrix`. The underscore-prefixed functions are implementation details — backtest is tightly coupled to their signatures. If optimize refactors its internals, backtest breaks silently. Either promote `_try_scipy_optimization` / `_grid_search_max_sharpe` to public API, or expose a single `optimize_weights(strategy, returns, cov, rf)` façade that backtest calls.

---

## Medium — `if __name__` demo blocks in production modules

These mix demo/test concerns with production code. Same issue we fixed in
`ingest_postgres.py` by extracting to `scripts/generate_benchmarks.py`.

- [x] **ingest.py** (lines 438–460)
- [x] **transform.py** (lines 579–616)
- [x] **optimize.py** (lines 893–927)
- [x] **backtest.py** (lines 486–487)
- [x] **ingest_scraping.py** (lines 367–400)
- [x] **ingest_sources.py** (lines 558–585)

**Fix**: Delete them. They add no test coverage (pytest never runs `__main__`), and anyone needing a quick test can use the one-liners in CLAUDE.md's "Commandes rapides" section.

---

## Medium — Service locator via `get_storage()` instead of injection

Multiple functions create their own storage internally via `get_storage(backend)`.
This is the service locator anti-pattern — same issue as `load_db_config()` inside
`_get_connection()` that the user flagged in the ingest_postgres review.

- [x] **transform.py**: `transform_data()` and `load_processed_metrics()` call `get_storage(storage_backend)`
- [x] **optimize.py**: `optimize_portfolio()`, `compute_and_save_frontier()`, `calculate_equal_weight_portfolio()`, `load_optimal_portfolio()` all call `get_storage()`
- [x] **backtest.py**: `run_backtest()` calls `get_storage(storage_backend)`

**Fix**: Accept a `Storage` instance (or None with fallback). Callers inject; functions don't resolve their own dependencies.

---

## Medium — Hardcoded magic number `365` in backtest.py

- [x] **backtest.py** `_compute_metrics()` (lines 289, 296, 300): Hardcodes `365` for annualization instead of using `_cfg.trading_days_per_year`. If the project ever switches to traditional market days (252), backtest and transform would diverge silently.

---

## Low — Fragile BTC-first assumption in backtest.py

- [x] **backtest.py** (line 386): `btc_weights = [1.0] + [0.0] * (n_symbols - 1)` assumes the first symbol in the data is always BTC. If symbol order changes (alphabetical sort, config change), the "BTC-only" benchmark becomes a random single-asset portfolio. Should find BTC by name.

---

## Low — Mutation of module-level data in ingest_scraping.py

- [x] **ingest_scraping.py** `_scrape_coingecko_alternative()` (line 273): Mutates dicts inside the module-level `sample_data` list (`item["scraped_at"] = ...`). On second call, the dicts already have stale `scraped_at` keys. Should copy before mutating.

---

## Low — `print()` utilities in transform.py

- [x] **transform.py** `print_correlation_matrix()` and `print_covariance_matrix()` (lines 531–572): Use `print()` directly. These are debug/demo helpers that don't belong in a production module. Either delete or move to a CLI script.

---

## Low — Redundant exception catch in ingest_sources.py

- [x] **ingest_sources.py** (line 453): `except (SourceError, Exception)` — `Exception` already covers `SourceError`. Should be just `except Exception`.
