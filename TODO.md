# TODO — Full Codebase Review

Chunked by priority. Work through one section at a time.

---

## ~~Critical (security + correctness)~~ ✅ DONE

- [x] **C-1**: SQL injection → parameterized queries in `duckdb.py`
- [x] **C-2**: Hardcoded secrets → `.env` file + `${VAR}` references in docker-compose
- [x] **C-3**: Sortino denominator bug → fixed to use all observations
- [x] **C-4**: Schema mismatch → verified: Parquet columns match views (non-issue)
- [x] **C-5**: API input validation → upfront symbol check in `/klines/{symbol}`

---

## ~~High (architecture + reliability)~~ ✅ DONE

- [x] **H-1**: Config caching → `@lru_cache` on `load_config()` + test fixture cache clear
- [x] **H-2**: DuckDB connection → `close()`, `__enter__`/`__exit__` context manager
- [x] **H-3**: Dockerfile.airflow → pinned version ranges for all deps
- [x] **H-4**: Dockerfile.streamlit → pinned version ranges
- [x] **H-5**: DAG factory pattern → verified: already uses `get_storage()` (non-issue)
- [x] **H-6**: Health checks → added for api + streamlit containers
- [x] **H-7**: Inline Python → extracted to `scripts/bootstrap.py`
- [x] **H-8**: Optimize duplication → extracted `_load_optimization_inputs()` helper
- [x] **H-9**: `__init__.py` exports → verified: both complete (non-issue)
- [x] **H-10**: Retry logic → verified: exponential backoff already exists in `_make_request()` (non-issue)
- [x] **H-11**: Exception handling → verified: fail-safe per source with aggregation (non-issue)

---

## ~~Medium (quality + performance)~~ ✅ DONE

- [x] **M-1**: Grid search fallback → Monte Carlo (Dirichlet) for >5 assets, grid for ≤5
- [x] **M-3**: CSV export → built-in to `st.dataframe` since Streamlit 1.28 (non-issue)
- [x] **M-5**: CORS → added `CORSMiddleware` for Streamlit origin
- [x] **M-6**: API pagination → `limit`/`offset` on `/klines/{symbol}` + OpenAPI spec updated
- [x] **M-7**: Logging → added `logging.basicConfig` with configurable `LOG_LEVEL`
- [x] **M-8**: Trading days → verified: already reads `cfg.trading_days_per_year` (non-issue)
- [x] **M-9**: Dashboard error handling → verified: `fetch_api` returns None, callers show `st.warning` (non-issue)
- [x] **M-10**: OpenAPI drift → verified: all 6 drift tests pass (non-issue)
- [x] **M-11**: pyproject.toml dev deps → verified: clean test/dev separation (non-issue)
- [x] **M-13**: Data freshness → "Last updated" from weights.json metadata in sidebar
- [ ] **M-2**: Incremental transform — skip (90-day window with 13 assets is fast enough)
- [ ] **M-4**: API rate limiting — skip (internal use only, not exposed to internet)
- [ ] **M-12**: Frontier caching — skip (recomputation is fast with scipy)

---

## Low (polish + nice-to-have)

- [x] **L-3**: `.dockerignore` → already exists with proper exclusions (non-issue)
- [ ] **L-1**: Pin `uv` version in Dockerfiles for reproducibility
- [ ] **L-2**: Docker Compose version field (optional in Compose v2)
- [ ] **L-4**: Timezone handling audit — verify UTC throughout pipeline
- [ ] **L-5**: README quick start — add `.env` setup instructions
- [ ] **L-6**: Add `src/py.typed` marker for type checking
- [ ] **L-7**: Git pre-commit hooks — `.pre-commit-config.yaml` with ruff + mypy
- [ ] **L-8**: Test coverage gaps — run `pytest --cov`, add tests for uncovered paths
- [ ] **L-9**: Airflow DAG unit tests — `test_dag.py` for parse validation
- [ ] **L-10**: Dashboard mobile responsiveness for jury demo
- [ ] **L-11**: Add `Makefile` with common targets
- [ ] **L-12**: French documentation spell check
