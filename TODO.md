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
- [ ] **SQL column names**: Slide 8 uses symbol_name/close_price/symbol_key but CHEAT_SHEET schema says symbol/close/symbol_id. Verify actual DuckDB schema.
- [x] **Service count**: Slide 22 says "5 services", docker-compose.yml has 8.

## Code review — Critical

- [ ] **API leaks raw exception details**: `str(e)` passed to HTTP 500 responses. Information disclosure risk. (`api/main.py:55,72,82,97,107,117`)
- [ ] **3 endpoints missing `response_model`**: `/portfolio`, `/portfolio/frontier`, `/portfolio/backtest` return untyped dicts. Breaks OpenAPI contract. (`api/main.py:75,100,110`)
- [ ] **Hardcoded `"parquet"` in API**: `get_storage_dep()` ignores `PipelineConfig.storage_backend`. (`api/main.py:29`)
- [ ] **Module-level config loading**: `_cfg = load_config()` at import time in 4 modules. Breaks DI, untestable, violates PipelineConfig mandate. (`ingest.py:40`, `transform.py:42`, `ingest_sources.py:38`, `ingest_postgres.py:34`)
- [ ] **Silent fallback to fake data**: Scraping and PostgreSQL modules return synthetic data on failure without clear indication. Corrupts analysis silently. (`ingest_scraping.py:230`, `ingest_postgres.py:603`)
- [ ] **DuckDB leaks through Storage ABC**: `query()`, `get_daily_returns()`, `get_summary_stats()` are DuckDB-only. Violates Liskov substitution. (`duckdb.py:107,287-325`)

## Code review — Medium

- [ ] **Broad `except Exception` in ingest**: Silently continues on symbol fetch failure, loses data without error propagation. (`ingest.py:262,343`)
- [ ] **Magic number `365`**: Hardcoded trading days instead of reading from config. (`transform.py:59`)
- [ ] **Duplicated `RISK_FREE_RATE` / `GRID_STEPS`**: Module globals duplicated from config. Coupling backtest→optimize. (`optimize.py:43-44`, `backtest.py:42`)
- [ ] **Fat `pipeline/__init__.py`**: Exports 55 items from all submodules. Internal changes ripple everywhere. (`pipeline/__init__.py`)
- [ ] **`_STORAGE_REGISTRY` is mutable global**: No protection against runtime mutation. Not thread-safe. (`storage/__init__.py:44`)
- [ ] **Inconsistent error handling**: Some modules wrap in custom exceptions, some catch-and-continue, some catch-and-re-raise. No single pattern.
- [ ] **`ingest_all_sources()` loses error info**: Returns which sources loaded, but not which failed or why. (`ingest_sources.py:378`)
- [ ] **Duplicated path calculation**: Same `Path(__file__).parent...` "find project root" logic in 4 files. (`parquet.py:56`, `duckdb.py:38`, `transform.py:44`, `ingest.py:40`)

## Code review — Low

- [ ] **`MetricResponse.data: dict`**: Untyped dict, should be `dict[str, Any]`. (`schemas.py:42`)
- [ ] **No input validation in optimize**: `calculate_portfolio_return()` doesn't check weights sum or vector lengths. (`optimize.py:116`)
- [ ] **Lazy imports**: `requests`, `BeautifulSoup`, `psycopg2` imported inside functions. Errors only surface at runtime. (`ingest_scraping.py:60`, `ingest_postgres.py:62`)
- [x] **Missing type hints on internals**: `_parse_html`, `_scrape_coingecko_alternative` soup param. (`_utils.py:96`, `ingest_scraping.py:230`)
