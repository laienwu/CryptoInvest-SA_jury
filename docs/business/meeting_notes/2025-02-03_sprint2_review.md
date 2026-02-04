# Sprint 2 Review - Data Processing & API

**Date:** 2025-02-03
**Time:** 14:00 - 15:30
**Sprint:** 2 (Data Processing)

## Attendees

| Name | Role | Present |
|------|------|---------|
| Marie Dupont | Product Owner | ✓ |
| Jean Martin | Business Analyst | ✓ |
| [Your Name] | Data Engineer | ✓ |
| Sophie Bernard | Data Analyst | ✓ |
| Pierre Durand | DevOps Engineer | ✓ |
| Lucas Petit | Scrum Master | ✓ |
| Thomas Leroy | IT Security | ✓ (Guest) |

---

## Sprint Goal

> Implement financial metrics calculation, DuckDB Data Warehouse, and REST API.

**Goal Status:** ✅ ACHIEVED

---

## Demo Summary

### 1. Financial Metrics Calculation ([Your Name])

**Demonstrated:**
- Log returns calculation: `r_t = ln(P_t / P_{t-1})`
- Annualized volatility: `σ × √365`
- Correlation matrix (Pearson)
- Covariance matrix (annualized)

**Sample Output:**
```
Volatility:
  BTCUSDT: 45.2% annualized
  ETHUSDT: 52.8% annualized
  SOLUSDT: 78.3% annualized

Correlation Matrix:
         BTC    ETH    SOL
  BTC   1.00   0.85   0.72
  ETH   0.85   1.00   0.78
  SOL   0.72   0.78   1.00
```

**Validation:**
- Sophie verified calculations match Excel reference (within 0.1%)

### 2. DuckDB Data Warehouse ([Your Name])

**Demonstrated:**
- Star schema implementation
- `fact_prices` - OHLCV data
- `dim_symbol` - Symbol dimension
- `dim_date` - Date dimension with calendar attributes

**Live SQL Query:**
```sql
SELECT symbol, AVG(close) as avg_price, COUNT(*) as records
FROM fact_prices
GROUP BY symbol
ORDER BY avg_price DESC;
```

**Performance:** Query on 450 records in < 10ms

### 3. REST API (Sophie)

**Demonstrated:**
- `GET /` - Health check
- `GET /symbols` - List available symbols
- `GET /klines/BTCUSDT` - Get price history
- `GET /metrics` - List available metrics
- `GET /portfolio` - Get optimal weights

**OpenAPI Documentation:**
- Auto-generated at `/docs`
- All endpoints documented with examples

**Response Time:** All endpoints < 200ms

### 4. Docker Deployment (Pierre)

**Demonstrated:**
- API container running on port 8000
- PostgreSQL benchmarks on port 5433
- Health check endpoint working
- Restart policy configured

---

## User Stories Completed

| Story ID | Title | Points | Status |
|----------|-------|--------|--------|
| US-003 | Calculate Financial Metrics | 5 | ✅ Done |
| US-007 | REST API for Data Access | 5 | ✅ Done |
| US-008 | SQL Query Interface | 5 | ✅ Done |

**Velocity:** 15 story points (vs 13 in Sprint 1)

---

## Stakeholder Feedback

**Marie (PO):**
> "The API demo was impressive. This is exactly what we need for the dashboard integration."

**Jean (BA):**
> "The correlation matrix will be very useful for diversification analysis. Can we export to Excel?"

**Action:** Add CSV export endpoint in Sprint 4

**Thomas (Security):**
> "API currently has no authentication. Is this acceptable?"

**Discussion:**
- MVP scope = no auth (internal use only)
- Production would need API keys or OAuth
- Documented as known limitation

---

## Technical Debt Identified

| Item | Priority | Sprint |
|------|----------|--------|
| Add API authentication | Medium | Post-MVP |
| Add request rate limiting | Low | Post-MVP |
| Improve error messages | Low | Sprint 4 |

---

## Sprint 3 Preview

**Goal:** Implement Markowitz optimization and Airflow orchestration

**Stories planned:**
- US-005: Markowitz Optimization (8 pts)
- US-009: Automated Pipeline Scheduling (5 pts)

**Capacity:** 13 points

---

## Metrics

| Metric | Sprint 1 | Sprint 2 | Trend |
|--------|----------|----------|-------|
| Velocity | 13 | 15 | ↑ |
| Bugs found | 2 | 1 | ↓ |
| Tech debt items | 1 | 3 | ↑ |
| Test coverage | 0% | 15% | ↑ |

---

## Risk Update

| Risk | Status | Notes |
|------|--------|-------|
| Binance API changes | Green | No issues |
| Data quality | Green | Validation working |
| Timeline | Green | On track |
| Single point of failure | Yellow | Need monitoring |

---

*Minutes recorded by: Lucas Petit*
*Sprint accepted by: Marie Dupont (Product Owner)*
