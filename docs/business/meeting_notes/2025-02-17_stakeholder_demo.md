# Stakeholder Demo - Portfolio Optimization MVP

**Date:** 2025-02-17
**Time:** 15:00 - 16:30
**Type:** Executive Demo

## Attendees

| Name | Role | Department |
|------|------|------------|
| François Martin | CTO | Executive |
| Marie Dupont | Product Owner | Business |
| Claire Rousseau | Head of Trading | Business |
| Jean Martin | Business Analyst | Business |
| [Your Name] | Data Engineer | Development |
| Sophie Bernard | Data Analyst | Development |
| Pierre Durand | DevOps Engineer | IT Operations |
| Lucas Petit | Scrum Master | PMO |

---

## Executive Summary

The Portfolio Optimization Platform MVP is **feature complete** and ready for user acceptance testing. The system automates data collection, analysis, and portfolio optimization for cryptocurrency investments.

**Key Achievement:** End-to-end pipeline running daily with < 5 minute execution time.

---

## Demo Agenda

1. Business Value Overview (5 min)
2. Live System Demo (30 min)
3. Technical Architecture (10 min)
4. Certification Compliance (10 min)
5. Roadmap & Next Steps (10 min)
6. Q&A (25 min)

---

## 1. Business Value Overview (Marie)

### Problem Statement
- Manual data collection: 2 hours/day
- Excel-based analysis: Error-prone, not scalable
- No systematic optimization: Gut-feel decisions

### Solution Delivered
- Automated daily data pipeline
- Professional-grade portfolio optimization
- API for integration with trading systems

### ROI Projection

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Data collection time | 2h/day | 0h/day | -100% |
| Analysis time | 1h/day | 5 min/day | -92% |
| Data freshness | T+1 day | T+0 | Real-time |
| Portfolio Sharpe | ~0.5 | ~1.2 | +140% |

---

## 2. Live System Demo ([Your Name])

### Demo Flow

**Step 1: Data Ingestion**
```
$ python -c "from src.pipeline import ingest_all_sources; ingest_all_sources()"

==================================================
MULTI-SOURCE INGESTION (C8) - 5 Source Types
==================================================

[Source 1/5] CSV File ✓
[Source 2/5] JSON File ✓
[Source 3/5] REST API ✓
[Source 4/5] Web Scraping ✓
[Source 5/5] PostgreSQL ✓

Sources loaded: 5/5
```

**Stakeholder Reaction:** Claire impressed by multi-source capability

**Step 2: Data Transformation**
```
$ python -c "from src.pipeline import transform_data; transform_data()"

Calculating volatility...
  BTCUSDT: 45.23% annualized
  ETHUSDT: 52.81% annualized
  ...

Correlation Matrix computed.
Covariance Matrix computed.
```

**Step 3: Portfolio Optimization**
```
$ python -c "from src.pipeline import optimize_portfolio; optimize_portfolio()"

==================================================
OPTIMAL PORTFOLIO
==================================================

Weights:
  BTCUSDT: 35.2%
  ETHUSDT: 24.8%
  BNBUSDT: 18.5%
  SOLUSDT: 12.3%
  ADAUSDT:  9.2%

Expected Return: 18.5%
Volatility:      28.3%
Sharpe Ratio:    1.24

Method: scipy (SLSQP optimization)
```

**François (CTO):** "What's the Sharpe ratio of equal weighting?"
**Answer:** "0.89 - our optimization improves it by 39%"

**Step 4: API Demo**
- Showed Swagger UI at `http://localhost:8000/docs`
- Live calls to `/symbols`, `/klines/BTCUSDT`, `/portfolio`
- Response times all < 200ms

**Step 5: Airflow DAG**
- Showed DAG visualization
- Daily schedule at 00:00 UTC
- Task dependencies: ingest → transform → optimize

---

## 3. Technical Architecture (Pierre)

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES (C8)                        │
│  [Binance API] [CSV] [JSON] [Web Scraping] [PostgreSQL]    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAKE (C18-C21)                      │
│  ┌─────────┐   ┌─────────┐   ┌─────────┐                   │
│  │ BRONZE  │──▶│ SILVER  │──▶│  GOLD   │                   │
│  │ (raw)   │   │(process)│   │(output) │                   │
│  └─────────┘   └─────────┘   └─────────┘                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 DATA WAREHOUSE (C13-C17)                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐            │
│  │ fact_prices│  │ dim_symbol │  │  dim_date  │            │
│  └────────────┘  └────────────┘  └────────────┘            │
│                     DuckDB + Star Schema                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    EXPOSURE (C12)                           │
│                    FastAPI REST                             │
│                  Docker + Airflow                           │
└─────────────────────────────────────────────────────────────┘
```

**François:** "All containerized?"
**Pierre:** "Yes, `docker compose up` starts everything."

---

## 4. Certification Compliance (Jean)

| Bloc | Competencies | Status |
|------|--------------|--------|
| Bloc 1: Project Management | C1-C7 | ✅ 100% |
| Bloc 2: Data Collection | C8-C12 | ✅ 100% |
| Bloc 3: Data Warehouse | C13-C17 | ✅ 100% |
| Bloc 4: Data Lake | C18-C21 | ✅ 100% |

**All 21 competencies covered.**

Documentation:
- 10 rapport chapters
- MERISE modeling (MCD/MLD/MPD)
- RGPD compliance analysis
- SCD Type 1/2 documentation

---

## 5. Roadmap

### Completed (MVP)
- ✅ Multi-source ingestion
- ✅ Data Lake architecture
- ✅ Star schema DWH
- ✅ Portfolio optimization
- ✅ REST API
- ✅ Airflow orchestration
- ✅ Docker deployment
- ✅ Full documentation

### Post-MVP Backlog
| Feature | Priority | Effort |
|---------|----------|--------|
| API authentication | High | 2 days |
| Email alerts | Medium | 1 day |
| More assets (top 20) | Medium | 1 day |
| Backtesting module | Low | 1 week |
| Web dashboard | Low | 2 weeks |

---

## 6. Q&A

**Q (François):** What's the disaster recovery plan?
**A (Pierre):** Docker volumes are persistent. Full rebuild from scratch takes < 10 minutes. Data can be re-fetched from APIs.

**Q (Claire):** Can this connect to our trading system?
**A ([Your Name]):** Yes, the API returns JSON. We'd need to build an adapter for your specific system.

**Q (François):** What's the total cost?
**A (Marie):** Zero licensing costs - all open source. Only compute resources (1 VM, 2 CPU, 2GB RAM).

**Q (Claire):** How accurate is the optimization?
**A (Sophie):** Backtested on 90 days shows the optimized portfolio outperforms equal-weight by 15-20% on risk-adjusted basis.

---

## Decisions

1. ✅ **MVP Approved** for production deployment
2. ✅ **UAT Phase** starts 2025-02-18 (1 week)
3. ✅ **Go-live target:** 2025-02-28
4. ✅ **Post-MVP:** API auth to be added before external exposure

---

## Action Items

| Action | Owner | Due |
|--------|-------|-----|
| UAT test plan | Jean | 2025-02-18 |
| Production deployment | Pierre | 2025-02-25 |
| User training session | Sophie | 2025-02-27 |
| Certification submission | [Your Name] | 2025-03-10 |

---

*Minutes recorded by: Lucas Petit*
*Approved by: François Martin (CTO)*
