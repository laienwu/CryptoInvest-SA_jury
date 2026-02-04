# Sprint 1 Review - Data Ingestion

**Date:** 2025-01-20
**Time:** 14:00 - 15:30
**Sprint:** 1 (Data Ingestion)

## Attendees

| Name | Role | Present |
|------|------|---------|
| Marie Dupont | Product Owner | ✓ |
| Jean Martin | Business Analyst | ✓ |
| [Your Name] | Data Engineer | ✓ |
| Sophie Bernard | Data Analyst | ✓ |
| Pierre Durand | DevOps Engineer | ✓ |
| Lucas Petit | Scrum Master | ✓ |

---

## Sprint Goal

> Implement automated data collection from multiple sources with storage in Data Lake architecture.

**Goal Status:** ✅ ACHIEVED

---

## Demo Summary

### 1. Binance API Integration ([Your Name])

**Demonstrated:**
- Live data fetch from Binance `/api/v3/klines` endpoint
- Configurable symbols (BTC, ETH, BNB, SOL, ADA)
- Configurable time period (90 days default)
- Retry logic with exponential backoff
- Rate limiting compliance

**Stakeholder Feedback:**
- Marie: "Can we add more symbols easily?" → Yes, via config.toml
- Jean: "What happens if API is down?" → Retry 3x, then fail with alert

### 2. Multi-Source Ingestion ([Your Name])

**Demonstrated:**
- CSV file reading (symbols_metadata.csv)
- JSON configuration loading (portfolio_config.json)
- Web scraping (CoinGecko market rankings)
- PostgreSQL connection (historical benchmarks)

**5 Source Types Implemented:**
| Source | Status | Demo |
|--------|--------|------|
| REST API (Binance) | ✅ | Live fetch |
| CSV File | ✅ | Metadata loaded |
| JSON File | ✅ | Config loaded |
| Web Scraping | ✅ | Rankings scraped |
| PostgreSQL | ✅ | Benchmarks queried |

**Stakeholder Feedback:**
- Pierre: "Good diversity of sources for certification" ✓
- Sophie: "Can I see the scraped data?" → Showed market rankings output

### 3. Data Lake Storage ([Your Name])

**Demonstrated:**
- Bronze zone: `data/raw/klines/*.parquet`
- Parquet format with schema enforcement
- Incremental ingestion (only new data)

**Metrics:**
- 5 symbols × 90 days = 450 records
- Storage size: ~50 KB (compressed)
- Ingestion time: ~5 seconds

### 4. Docker Environment (Pierre)

**Demonstrated:**
- `docker compose up api` - API running
- `docker compose --profile pipeline up` - Pipeline execution
- Volume mounts for data persistence

---

## User Stories Completed

| Story ID | Title | Points | Status |
|----------|-------|--------|--------|
| US-001 | Automated Price Collection | 5 | ✅ Done |
| US-002 | Multi-Source Data Integration | 8 | ✅ Done |

**Velocity:** 13 story points

---

## User Stories Not Completed

None - Sprint goal fully achieved.

---

## Impediments Encountered

| Impediment | Resolution |
|------------|------------|
| CoinGecko page structure changed | Implemented fallback scraping method |
| PostgreSQL connection timeout | Added connection retry logic |

---

## Stakeholder Questions & Answers

**Q (Marie):** Is the data quality validated?
**A:** Basic validation (null checks) implemented. Full validation in Sprint 2.

**Q (Jean):** How do we know if ingestion failed?
**A:** Currently logs to stdout. Alerting will be added in Sprint 4.

**Q (Sophie):** Can I query the data with SQL?
**A:** Yes, DuckDB integration coming in Sprint 2.

---

## Action Items from Review

| Action | Owner | Due |
|--------|-------|-----|
| Add configurable symbol list to docs | Jean | Sprint 2 |
| Document API error codes | [Your Name] | Sprint 2 |
| Plan monitoring approach | Pierre | Sprint 2 |

---

## Sprint 2 Preview

**Goal:** Implement data transformation and DuckDB Data Warehouse

**Stories planned:**
- US-003: Calculate Financial Metrics (5 pts)
- US-007: REST API for Data Access (5 pts)
- US-008: SQL Query Interface (5 pts)

**Capacity:** 15 points

---

## Retrospective Actions (from separate retro)

| What went well | What to improve |
|----------------|-----------------|
| Multi-source implementation ahead of schedule | Need more unit tests |
| Good collaboration between DE and DevOps | Documentation could be more detailed |
| Clear requirements from Business | Earlier stakeholder demos |

---

*Minutes recorded by: Lucas Petit*
*Sprint accepted by: Marie Dupont (Product Owner)*
