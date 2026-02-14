# TODO — Repo Cleanup

## Bugs
- [x] **Dockerfiles Python version**: pyproject.toml requires >=3.13 but Dockerfile/Dockerfile.streamlit use 3.12-slim, Dockerfile.airflow uses 3.11. Update base images.
- [x] **OpenAPI spec vs actual API**: HealthResponse fields wrong, /symbols returns wrapped object not array, /klines has phantom query params, /portfolio/summary missing from spec.
- [x] **`--profile full` doesn't start Airflow**: docker-compose.yml only assigns `full` to postgres-benchmarks. Airflow services need `full` profile too, or fix docs.

## Stale docs
- [x] **Test count**: README says 124, CHEAT_SHEET says 165, CLAUDE.md/slides say 208. Run pytest, update all.
- [x] **Coverage %**: README says 43%, CHEAT_SHEET says 46%. Run coverage, update both.
- [x] **README project structure**: Missing ingest_scraping.py, ingest_postgres.py, backtest.py, schemas.py, config.py, _utils.py.
- [x] **README config example**: Shows fake `[optimization]` section that doesn't exist in config.toml or load_config().
- [x] **README API endpoints**: Lists 7 of 10. Missing /metrics/{name}, /portfolio/frontier, /portfolio/backtest. Also fix slides (missing /portfolio/summary) and CHEAT_SHEET checklist ("9 endpoints").

## Minor code
- [x] **DuckDB "(Future)" docstring**: storage/__init__.py says DuckDB is future but it's already imported and registered.
- [x] **DuckDBStorage missing from `__all__`**: storage/__init__.py exports ParquetStorage but not DuckDBStorage.
- [x] **Useless `tomli` in Dockerfile.airflow**: Code uses stdlib `tomllib`. Remove the pip install.
- [x] **`scipy` undeclared**: Used in optimize.py but not in pyproject.toml. Add as optional dependency.

## Slides
- [x] **SQL column names**: Slide 8 fixed to use actual DuckDB column names (`symbol`, `close`, `symbol_id`).
- [x] **Service count**: Slide 22 says "5 services", docker-compose.yml has 8.

## Code review — Critical

- [x] **API leaks raw exception details**: `str(e)` passed to HTTP 500 responses. Information disclosure risk. (`api/main.py:55,72,82,97,107,117`)
- [x] **3 endpoints missing `response_model`**: `/portfolio`, `/portfolio/frontier`, `/portfolio/backtest` return untyped dicts. Breaks OpenAPI contract. (`api/main.py:75,100,110`)
- [x] **Hardcoded `"parquet"` in API**: `get_storage_dep()` ignores `PipelineConfig.storage_backend`. (`api/main.py:29`)
- [x] **Module-level config loading**: `transform.py` replaced custom `_load_config()` with centralized `load_config()`. (`transform.py:42`)
- [x] **Silent fallback to fake data**: Scraping fallback now opt-in via `allow_fallback` param. Default raises `ScrapingError`. (`ingest_scraping.py:122`)
- [x] **DuckDB leaks through Storage ABC**: Documented as intentional (interface segregation for C9/C13). ABC docstring updated. (`base.py:34`, `duckdb.py:287`)

## Code review — Medium

- [x] **Broad `except Exception` in ingest**: Reviewed — `fetch_all_symbols` uses specific `BinanceAPIError`, not broad `Exception`. `ingest_incremental` fallback-to-empty is intentional for resilience. No change needed.
- [x] **Magic number `365`**: Now reads from `PipelineConfig.trading_days_per_year` via `load_config()`. (`transform.py`)
- [x] **Duplicated `RISK_FREE_RATE` / `GRID_STEPS`**: `backtest.py` now reads `RISK_FREE_RATE` from `load_config()` directly instead of importing from `optimize.py`.
- [x] **Fat `pipeline/__init__.py`**: Trimmed from 47 to 22 exports. Internal helpers removed; import from submodules directly.
- [x] **`_STORAGE_REGISTRY` is mutable global**: Now uses `MappingProxyType` read-only proxy. Mutations go through `register_storage()` only.
- [x] **Inconsistent error handling**: Documented as intentional per-domain pattern in `pipeline/__init__.py` docstring. Ingest = best-effort (continue), transform/optimize/backtest = all-or-nothing (reraise).
- [x] **`ingest_all_sources()` loses error info**: Now tracks `failures` list with source name and error message in result dict.
- [x] **Duplicated path calculation**: `transform.py` and `ingest.py` now use `load_config()`. Storage modules (`parquet.py`, `duckdb.py`) keep own defaults intentionally — storage layer is independent of pipeline config.

## Code review — Rewrite

- [x] **`ingest_postgres.py` rewrite**: Removed duplicate `SCHEMA_SQL`/`initialize_schema()` (handled by `init-benchmarks.sql`), extracted demo data generation to `scripts/generate_benchmarks.py`, replaced module-level `DB_CONFIG` with frozen `DatabaseConfig` dataclass + `load_db_config()` in `config.py`, added context managers for all DB connections/cursors, fixed `load_benchmarks_fallback()` global RNG state leak.

## Code review — Low

- [x] **`MetricResponse.data: dict`**: Untyped dict, should be `dict[str, Any]`. (`schemas.py:42`)
- [x] **No input validation in optimize**: Added `_validate_weights()` — checks length match and sum ≈ 1.0. Called from `calculate_portfolio_return()` and `calculate_portfolio_variance()`.
- [x] **Lazy imports**: By design — `requests`, `beautifulsoup4`, `psycopg2` are optional deps with explicit `ImportError` messages guiding installation. No change needed.
- [x] **Missing type hints on internals**: `_parse_html`, `_scrape_coingecko_alternative` soup param. (`_utils.py:96`, `ingest_scraping.py:230`)
