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
- [x] **K-10**: Dockerfile.streaming for producer/consumer
- [x] **K-11**: docker-compose `--profile streaming` with producer + consumer services
- [x] **K-12**: Update architecture docs (C4, CLAUDE.md, README)
- [x] **K-13**: Tests for producer/consumer (10 tests, 256 total)

---

## Data Quality — Custom Validation Framework (new feature)

Lightweight validation contracts on pipeline data. No external deps — pure Python/PyArrow.

### Validation Rules
- [x] **DQ-3**: `src/pipeline/validation.py` — ValidationResult/ValidationReport dataclasses
- [x] **DQ-4**: Bronze: ohlcv_schema, no_null_ohlcv, positive_close, non_negative_volume, high_gte_low, timestamp_not_empty, min_records
- [x] **DQ-5**: Silver: returns_in_range, volatility_positive, correlation (symmetric/diagonal/range), covariance_symmetric
- [x] **DQ-6**: Gold: weights_sum_to_one, weights_non_negative, weights_bounded, has_expected_return, has_volatility, has_sharpe_ratio

### Integration
- [x] **DQ-7**: `validate_stage()` dispatcher for bronze/silver/gold
- [ ] **DQ-8**: Airflow DAG tasks — skip (requires DAG refactor)
- [x] **DQ-9**: Tests for validation suites (40 tests)
- [x] **DQ-10**: Update docs (CLAUDE.md, pipeline __init__.py)

---

## MinIO Object Storage (new feature)

Replace local `data/` with S3-compatible object storage. Proves cloud-native data lake pattern.

### Infrastructure
- [x] **S3-1**: Add MinIO service to docker-compose (`--profile storage`)
- [x] **S3-2**: Add `MINIO_*` env vars to `.env.example` and `config.py`
- [x] **S3-3**: Add `minio` to pyproject.toml optional deps

### Storage Backend
- [x] **S3-4**: `src/storage/minio.py` — new Storage ABC implementation (S3 API)
- [x] **S3-5**: Register in `_STORAGE_REGISTRY` with `STORAGE_BACKEND=minio` selector
- [x] **S3-6**: Bronze/Silver/Gold zone mapping to S3 prefixes (raw/, processed/, output/)

### Integration
- [x] **S3-7**: All pipeline stages work transparently via Storage ABC (no code changes needed)
- [x] **S3-8**: Tests for MinIO storage backend (22 tests, mocked client)
- [x] **S3-9**: Update docs (CLAUDE.md, README, architecture)

---

## Redis API Caching (new feature)

Cache FastAPI responses with TTL. Demonstrates caching patterns and performance optimization.

### Infrastructure
- [x] **R-1**: Add Redis service to docker-compose (`--profile cache`)
- [x] **R-2**: Add `REDIS_URL` env var to `.env.example`
- [x] **R-3**: Add `redis` to pyproject.toml optional deps

### Implementation
- [x] **R-4**: `src/api/cache.py` — RedisCache class + cached_response helper
- [x] **R-5**: Apply caching to `/portfolio`, `/portfolio/frontier`, `/portfolio/backtest`, `/metrics/{name}`
- [x] **R-6**: Cache invalidation via TTL expiry (300s)

### Integration
- [x] **R-7**: Graceful fallback when Redis is unavailable (get_cache returns None)
- [x] **R-8**: Tests for cache hit/miss/invalidation (17 tests)
- [x] **R-9**: Update docs (CLAUDE.md)

---

## Prometheus + Grafana Monitoring (new feature)

Production observability: metrics endpoint, dashboards, alerting rules.

### Infrastructure
- [x] **MON-1**: Add Prometheus + Grafana services to docker-compose (`--profile monitoring`)
- [x] **MON-2**: Prometheus scrape config (`monitoring/prometheus.yml`)
- [x] **MON-3**: Grafana provisioned dashboard (`monitoring/grafana/`)

### Metrics
- [x] **MON-4**: FastAPI `/prom/metrics` endpoint (prometheus-fastapi-instrumentator)
- [x] **MON-5**: Custom business metrics: pipeline_last_run, records_ingested, portfolio_sharpe
- [ ] **MON-6**: Kafka consumer lag metric — skip (requires Kafka running)

### Integration
- [x] **MON-7**: Alerting rules (`monitoring/alerts.yml` — latency, error rate)
- [x] **MON-8**: Tests for metrics endpoint (7 tests)
- [x] **MON-9**: Update docs (CLAUDE.md, OpenAPI spec)
