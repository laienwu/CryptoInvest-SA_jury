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

## ~~Low (polish + nice-to-have)~~ ✅ DONE

- [x] **L-1**: Pin uv → `"uv>=0.9,<1"` in Dockerfile + Dockerfile.streamlit
- [x] **L-3**: `.dockerignore` → already exists (non-issue)
- [x] **L-4**: Timezone → verified: Binance returns UTC, stored as strings consistently (non-issue)
- [x] **L-5**: README → added `.env` setup section + fixed test badge (214→246 current suite)
- [x] **L-6**: `src/py.typed` marker created
- [x] **L-7**: `.pre-commit-config.yaml` with ruff + mypy
- [x] **L-8**: Coverage at 55% (246 tests) — gaps are integration paths, acceptable
- [x] **L-11**: `Makefile` with test/lint/typecheck/check/build/up/down/bootstrap/clean
- [ ] **L-2**: Docker Compose version field — skip (optional in Compose v2)
- [ ] **L-9**: Airflow DAG tests — skip (requires airflow as test dep)
- [ ] **L-10**: Dashboard mobile — manual testing before soutenance
- [ ] **L-12**: French spell check — manual task before soutenance

---

## Kafka Streaming Ingestion (new feature)

Real-time ingestion path alongside existing batch pipeline.
Architecture: `Binance WebSocket → Kafka → Consumer → Bronze Parquet`
Airflow stays as orchestrator for downstream (transform → optimize → frontier → backtest).

### Infrastructure
- [x] **K-1**: Add Redpanda (Kafka-compatible) + console services to docker-compose
- [x] **K-2**: Add `KAFKA_*` env vars to `.env.example`
- [x] **K-3**: Kafka topic creation (`klines-raw`) via redpanda-init container

### Producer
- [x] **K-4**: `src/pipeline/stream_producer.py` — Binance WebSocket → Kafka topic
- [x] **K-5**: Serialize kline messages as JSON with symbol, timestamp, OHLCV fields
- [x] **K-6**: Reconnection logic + graceful shutdown (SIGINT/SIGTERM)

### Consumer
- [x] **K-7**: `src/pipeline/stream_consumer.py` — Kafka topic → micro-batch Parquet
- [x] **K-8**: Buffer 100 records or 60s, flush to `data/raw/klines/` as Parquet
- [x] **K-9**: Deduplicate with existing batch data (same timestamp = skip)

### Integration
- [ ] **K-10**: Dockerfile.kafka for producer/consumer
- [ ] **K-11**: docker-compose profile `--profile streaming`
- [ ] **K-12**: Update architecture docs (C4, CLAUDE.md, README)
- [ ] **K-13**: Tests for producer/consumer (mock WebSocket + mock Kafka)
