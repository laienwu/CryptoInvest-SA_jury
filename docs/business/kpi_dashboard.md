# KPI Dashboard Specification

## 1. Executive Summary Dashboard

### 1.1 Portfolio Performance KPIs

| KPI | Target | Threshold | Data Source |
|-----|--------|-----------|-------------|
| **Sharpe Ratio** | > 1.0 | < 0.5 = Red | optimize.py |
| **Annual Return** | > 15% | < 5% = Red | optimize.py |
| **Volatility** | < 30% | > 50% = Red | optimize.py |
| **Max Drawdown** | < 20% | > 30% = Red | calculated |
| **Tracking Error vs Benchmark** | < 10% | > 20% = Red | benchmark comparison |

### 1.2 Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                    PORTFOLIO OPTIMIZATION DASHBOARD              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ SHARPE RATIO │  │   RETURN     │  │  VOLATILITY  │           │
│  │    1.24      │  │   +18.5%     │  │    28.3%     │           │
│  │   ▲ +0.15    │  │   ▲ +2.1%    │  │   ▼ -1.2%    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              PORTFOLIO ALLOCATION                        │    │
│  │  ┌─────┐                                                 │    │
│  │  │ BTC │████████████████████████░░░░░░░  35%             │    │
│  │  │ ETH │████████████████░░░░░░░░░░░░░░░  25%             │    │
│  │  │ SOL │██████████░░░░░░░░░░░░░░░░░░░░░  15%             │    │
│  │  │ BNB │████████░░░░░░░░░░░░░░░░░░░░░░░  12%             │    │
│  │  │ ADA │██████░░░░░░░░░░░░░░░░░░░░░░░░░   8%             │    │
│  │  │OTHER│████░░░░░░░░░░░░░░░░░░░░░░░░░░░   5%             │    │
│  │  └─────┘                                                 │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           PERFORMANCE VS BENCHMARK (90 days)             │    │
│  │                                                          │    │
│  │  120% ┤                              ╭─── Portfolio      │    │
│  │       │                           ╭──╯                   │    │
│  │  110% ┤                      ╭────╯                      │    │
│  │       │               ╭──────╯    ╭─── BTC Benchmark    │    │
│  │  100% ┼───────────────╯──────────╯                       │    │
│  │       │                                                  │    │
│  │   90% ┤                                                  │    │
│  │       └──────────────────────────────────────────────    │    │
│  │        Jan        Feb        Mar        Apr              │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Operational KPIs

### 2.1 Data Pipeline Health

| KPI | Target | Measurement | Alert Threshold |
|-----|--------|-------------|-----------------|
| **Pipeline Success Rate** | 99% | Successful runs / Total runs | < 95% |
| **Data Freshness** | < 24h | Time since last update | > 48h |
| **Ingestion Latency** | < 5 min | End-to-end pipeline time | > 15 min |
| **Data Completeness** | 100% | Non-null records / Expected records | < 98% |
| **API Uptime** | 99.5% | Uptime / Total time | < 99% |

### 2.2 Operational Dashboard Layout

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPERATIONS DASHBOARD                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PIPELINE STATUS                    LAST 7 DAYS                  │
│  ┌────────────────────────┐        ┌─────────────────────────┐  │
│  │ ● Ingest      ✓ OK     │        │ Mon ████████████ 100%   │  │
│  │ ● Transform   ✓ OK     │        │ Tue ████████████ 100%   │  │
│  │ ● Optimize    ✓ OK     │        │ Wed ██████████░░  95%   │  │
│  │ ● API         ✓ OK     │        │ Thu ████████████ 100%   │  │
│  │                        │        │ Fri ████████████ 100%   │  │
│  │ Last run: 2h ago       │        │ Sat ████████████ 100%   │  │
│  │ Next run: in 22h       │        │ Sun ████████████ 100%   │  │
│  └────────────────────────┘        └─────────────────────────┘  │
│                                                                  │
│  DATA QUALITY                       SYSTEM RESOURCES             │
│  ┌────────────────────────┐        ┌─────────────────────────┐  │
│  │ Records: 2,450         │        │ CPU:    ██░░░░░░  25%   │  │
│  │ Symbols: 5             │        │ Memory: ████░░░░  45%   │  │
│  │ Date range: 90 days    │        │ Disk:   ██░░░░░░  18%   │  │
│  │ Null values: 0         │        │ Network: OK             │  │
│  │ Duplicates: 0          │        │                         │  │
│  └────────────────────────┘        └─────────────────────────┘  │
│                                                                  │
│  RECENT ALERTS                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ⚠ 2025-01-15 08:32  Warning: API response time > 400ms   │   │
│  │ ✓ 2025-01-14 00:05  Info: Daily pipeline completed       │   │
│  │ ✓ 2025-01-13 00:04  Info: Daily pipeline completed       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. Business Value KPIs

### 3.1 ROI Metrics

| Metric | Calculation | Target |
|--------|-------------|--------|
| **Time Saved** | Manual hours before - Manual hours after | > 20h/month |
| **Decision Speed** | Time to generate portfolio recommendation | < 5 minutes |
| **Data Coverage** | Assets tracked / Assets in market | > 80% top 100 |
| **Analysis Accuracy** | Backtested return vs Actual return | < 5% deviation |

### 3.2 Adoption Metrics

| Metric | Target | Current |
|--------|--------|---------|
| API calls per day | > 100 | Tracking |
| Unique users per week | > 5 | Tracking |
| Reports generated per month | > 20 | Tracking |
| Feature requests addressed | > 80% | Tracking |

---

## 4. Technical Implementation

### 4.1 Data Sources for KPIs

```python
# KPI Data Sources
KPI_SOURCES = {
    "sharpe_ratio": "data/output/weights.json",
    "annual_return": "data/output/weights.json",
    "volatility": "data/output/weights.json",
    "pipeline_status": "airflow_api/dag_runs",
    "data_freshness": "data/raw/klines/*.parquet (mtime)",
    "api_uptime": "docker_healthcheck",
    "record_count": "SELECT COUNT(*) FROM fact_prices",
}
```

### 4.2 Refresh Frequency

| Dashboard | Refresh Rate | Data Latency |
|-----------|--------------|--------------|
| Executive | Daily | T+1 day |
| Operational | Real-time | < 1 minute |
| Business Value | Weekly | T+1 week |

### 4.3 Alert Configuration

```yaml
alerts:
  - name: pipeline_failure
    condition: pipeline_success_rate < 0.95
    severity: critical
    channel: email, slack

  - name: data_stale
    condition: data_freshness > 48h
    severity: warning
    channel: slack

  - name: sharpe_low
    condition: sharpe_ratio < 0.5
    severity: info
    channel: email
```

---

## 5. Access Control

| Role | Executive Dashboard | Operations Dashboard | Raw Data |
|------|--------------------|--------------------|----------|
| Executive | View | View summary | No |
| Portfolio Manager | View | View | Read |
| Data Engineer | View | Full access | Full access |
| DevOps | View summary | Full access | Read |
