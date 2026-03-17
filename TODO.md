# TODO — Project Status

All engineering work complete. 342 tests passing. Remaining items are soutenance prep only.

---

## Completed Features

| Feature | Tests | Key files |
|---------|-------|-----------|
| Pipeline (ingest → transform → optimize → frontier → backtest) | 148 | `src/pipeline/` |
| Storage ABC (Parquet + DuckDB + MinIO) | 60 | `src/storage/` |
| FastAPI REST API (9 endpoints) | 22 | `src/api/main.py` |
| Kafka streaming (Redpanda + producer + consumer) | 10 | `src/pipeline/stream_*.py` |
| Data quality validation (bronze/silver/gold) | 40 | `src/pipeline/validation.py` |
| MinIO S3-compatible storage | 22 | `src/storage/minio.py` |
| Redis API caching (TTL + fallback) | 17 | `src/api/cache.py` |
| Prometheus + Grafana monitoring | 7 | `src/api/metrics.py`, `monitoring/` |
| OpenAPI drift detection | 6 | `tests/test_openapi_drift.py` |
| Config loading (TOML + env) | 10 | `src/config.py` |
| **Total** | **342** | |

## Completed Code Review (all items resolved)

- **Critical (C-1→C-5)**: SQL injection, secrets, Sortino bug, schema, input validation
- **High (H-1→H-11)**: Config caching, DuckDB lifecycle, Dockerfiles, DAG, health checks
- **Medium (M-1→M-13)**: Monte Carlo, CORS, pagination, logging, data freshness
- **Low (L-1→L-11)**: Pin uv, py.typed, pre-commit, coverage, Makefile

## Skipped (intentional)

- M-2: Incremental transform — 90-day window is fast enough
- M-4: API rate limiting — internal use only
- M-12: Frontier caching — scipy recomputation is fast
- L-2: Docker Compose version — optional in v2
- L-9: Airflow DAG tests — requires airflow as test dep
- DQ-8: Airflow validation tasks — requires DAG refactor
- MON-6: Kafka consumer lag — requires Kafka running

---

## Soutenance Prep

- [x] **SP-1**: Generate HTML slides from `slides_soutenance.md`
- [ ] **SP-2**: Demo dry run — test all Docker profiles end-to-end
- [ ] **SP-3**: Dashboard mobile check (L-10)
- [ ] **SP-4**: French spell check on docs (L-12)
- [ ] **SP-5**: Print/export documentation for jury
