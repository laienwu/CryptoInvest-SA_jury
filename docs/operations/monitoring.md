# Monitoring & Alerting Guide

## Overview

This document describes the monitoring strategy for the Portfolio Optimization Platform. It covers metrics collection, alerting rules, and dashboard specifications.

---

## 1. Monitoring Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MONITORING STACK                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐        │
│  │   Services    │───▶│   Metrics     │───▶│   Alerting    │        │
│  │               │    │   Collector   │    │               │        │
│  │ • API         │    │               │    │ • Email       │        │
│  │ • Airflow     │    │ • Health      │    │ • Slack       │        │
│  │ • Pipeline    │    │ • Logs        │    │               │        │
│  └───────────────┘    └───────────────┘    └───────────────┘        │
│                              │                                       │
│                              ▼                                       │
│                    ┌───────────────────┐                            │
│                    │    Dashboard      │                            │
│                    │                   │                            │
│                    │ • Airflow UI      │                            │
│                    │ • Docker stats    │                            │
│                    │ • Custom scripts  │                            │
│                    └───────────────────┘                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Key Metrics

### 2.1 Application Metrics

| Metric | Type | Source | Alert Threshold |
|--------|------|--------|-----------------|
| API response time | Gauge | FastAPI | > 500ms |
| API error rate | Counter | FastAPI logs | > 5% |
| API requests/min | Counter | FastAPI | < 1 (no traffic warning) |
| Pipeline duration | Gauge | Airflow | > 10 minutes |
| Pipeline success rate | Percentage | Airflow | < 95% |
| Data freshness | Gauge | File mtime | > 24 hours |

### 2.2 Infrastructure Metrics

| Metric | Type | Source | Alert Threshold |
|--------|------|--------|-----------------|
| Container CPU | Gauge | Docker stats | > 80% |
| Container memory | Gauge | Docker stats | > 80% |
| Disk usage | Gauge | df | > 85% |
| Container restarts | Counter | Docker events | > 3/hour |

### 2.3 Business Metrics

| Metric | Type | Source | Alert Threshold |
|--------|------|--------|-----------------|
| Portfolio Sharpe ratio | Gauge | weights.json | < 0.5 |
| Data records count | Gauge | DuckDB | < expected |
| Symbol coverage | Percentage | Data Lake | < 100% |

---

## 3. Health Checks

### 3.1 API Health Check

**Endpoint:** `GET /`

**Implementation:**
```python
@app.get("/")
def health_check():
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }
```

**Docker health check:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

### 3.2 Deep Health Check

**Endpoint:** `GET /health/deep` (to implement)

**Checks:**
- Database connectivity (DuckDB)
- Data freshness (file timestamps)
- External API reachability (Binance)

```python
@app.get("/health/deep")
def deep_health_check():
    checks = {
        "database": check_duckdb(),
        "data_freshness": check_data_freshness(),
        "binance_api": check_binance(),
    }
    status = "healthy" if all(c["ok"] for c in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
```

### 3.3 Airflow Health Check

**Endpoint:** `GET http://localhost:8081/health`

**CLI check:**
```bash
docker compose exec airflow-webserver airflow jobs check --job-type SchedulerJob
```

---

## 4. Logging

### 4.1 Log Format

**Standard format (JSON):**
```json
{
  "timestamp": "2025-01-15T08:32:15.123Z",
  "level": "INFO",
  "service": "api",
  "message": "Request processed",
  "request_id": "abc-123",
  "duration_ms": 45,
  "path": "/portfolio"
}
```

### 4.2 Log Levels

| Level | Usage | Examples |
|-------|-------|----------|
| ERROR | Failures requiring attention | API errors, pipeline failures |
| WARNING | Potential issues | Slow responses, rate limiting |
| INFO | Normal operations | Request processed, task completed |
| DEBUG | Detailed debugging | Query results, intermediate values |

### 4.3 Log Collection

```bash
# View real-time logs
docker compose logs -f --tail=100

# Filter by service
docker compose logs api | grep ERROR

# Save logs to file
docker compose logs > logs/$(date +%Y%m%d).log
```

### 4.4 Log Retention

| Log Type | Retention | Location |
|----------|-----------|----------|
| Application logs | 30 days | Docker/journald |
| Airflow task logs | 90 days | ./logs/airflow/ |
| Access logs | 90 days | ./logs/access/ |

---

## 5. Alerting Rules

### 5.1 Critical Alerts (P1)

**Trigger immediate notification (email + Slack)**

| Alert | Condition | Action |
|-------|-----------|--------|
| API Down | Health check fails 3x | Restart container, escalate |
| Pipeline Failed | DAG run failed | Check logs, manual retry |
| Data Corruption | Invalid data detected | Stop pipeline, investigate |

### 5.2 Warning Alerts (P2)

**Trigger notification within 1 hour**

| Alert | Condition | Action |
|-------|-----------|--------|
| High Latency | API p95 > 500ms | Check resources |
| Data Stale | No update in 24h | Check Airflow scheduler |
| Low Sharpe | Sharpe < 0.5 | Notify analysts |

### 5.3 Informational Alerts (P3)

**Logged, reviewed daily**

| Alert | Condition | Action |
|-------|-----------|--------|
| High CPU | > 70% sustained | Consider scaling |
| Disk 75% | Disk usage > 75% | Plan cleanup |
| Rate Limited | Binance 429 error | Monitor frequency |

### 5.4 Alert Configuration

```yaml
# alerts.yml
alerts:
  - name: api_down
    severity: critical
    condition: health_check_failed
    for: 5m
    channels: [email, slack]
    message: "API health check failing for 5 minutes"

  - name: pipeline_failed
    severity: critical
    condition: dag_run_failed
    channels: [email, slack]
    message: "Portfolio optimization pipeline failed"

  - name: data_stale
    severity: warning
    condition: data_age > 24h
    channels: [slack]
    message: "Data not updated in 24 hours"

  - name: high_latency
    severity: warning
    condition: api_p95_latency > 500ms
    for: 10m
    channels: [slack]
    message: "API latency elevated"
```

---

## 6. Monitoring Scripts

### 6.1 Health Check Script

```bash
#!/bin/bash
# scripts/health_check.sh

API_URL="http://localhost:8000"
AIRFLOW_URL="http://localhost:8081/health"

# Check API
api_status=$(curl -s -o /dev/null -w "%{http_code}" $API_URL)
if [ "$api_status" != "200" ]; then
    echo "CRITICAL: API returned $api_status"
    exit 2
fi

# Check Airflow
airflow_status=$(curl -s -o /dev/null -w "%{http_code}" $AIRFLOW_URL)
if [ "$airflow_status" != "200" ]; then
    echo "WARNING: Airflow returned $airflow_status"
    exit 1
fi

# Check data freshness
data_age=$(find data/raw/klines -name "*.parquet" -mmin +1440 | wc -l)
if [ "$data_age" -gt 0 ]; then
    echo "WARNING: Data older than 24 hours"
    exit 1
fi

echo "OK: All checks passed"
exit 0
```

### 6.2 Metrics Collection Script

```python
#!/usr/bin/env python3
# scripts/collect_metrics.py

import json
import subprocess
from datetime import datetime
from pathlib import Path

def collect_metrics():
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "api": check_api(),
        "data": check_data(),
        "resources": check_resources(),
    }
    return metrics

def check_api():
    import requests
    try:
        r = requests.get("http://localhost:8000/", timeout=5)
        return {"status": "up", "response_time_ms": r.elapsed.total_seconds() * 1000}
    except Exception as e:
        return {"status": "down", "error": str(e)}

def check_data():
    parquet_files = list(Path("data/raw/klines").glob("*.parquet"))
    newest = max(f.stat().st_mtime for f in parquet_files) if parquet_files else 0
    age_hours = (datetime.now().timestamp() - newest) / 3600
    return {
        "files": len(parquet_files),
        "age_hours": round(age_hours, 1),
    }

def check_resources():
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        capture_output=True, text=True
    )
    return [json.loads(line) for line in result.stdout.strip().split("\n") if line]

if __name__ == "__main__":
    metrics = collect_metrics()
    print(json.dumps(metrics, indent=2))
```

---

## 7. Dashboards

### 7.1 Airflow Dashboard

**URL:** http://localhost:8081

**Key views:**
- DAGs: List of all DAGs with status
- Grid: Task execution history
- Graph: DAG structure visualization
- Logs: Task-level logs

### 7.2 Custom Monitoring Dashboard

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYSTEM STATUS DASHBOARD                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SERVICES                          LAST PIPELINE RUN             │
│  ┌────────────────────────┐       ┌────────────────────────┐    │
│  │ ● API          [UP]    │       │ Status:    ✓ Success   │    │
│  │ ● Airflow      [UP]    │       │ Duration:  3m 42s      │    │
│  │ ● Scheduler    [UP]    │       │ Records:   2,450       │    │
│  │ ● Database     [UP]    │       │ Started:   00:00 UTC   │    │
│  └────────────────────────┘       └────────────────────────┘    │
│                                                                  │
│  RESOURCES                         DATA QUALITY                  │
│  ┌────────────────────────┐       ┌────────────────────────┐    │
│  │ CPU:     ██░░░░░  25%  │       │ Symbols:   5/5  100%   │    │
│  │ Memory:  ████░░░  45%  │       │ Records:   2,450       │    │
│  │ Disk:    ██░░░░░  18%  │       │ Freshness: 2h ago      │    │
│  │ Network: OK            │       │ Nulls:     0           │    │
│  └────────────────────────┘       └────────────────────────┘    │
│                                                                  │
│  ALERTS (Last 24h)                                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ⚠ 08:32  API response time > 400ms (resolved)            │   │
│  │ ✓ 00:05  Daily pipeline completed successfully           │   │
│  │ ✓ 00:04  Previous day pipeline completed                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Notification Channels

### 8.1 Email Configuration

```yaml
# For Airflow email alerts
smtp:
  host: smtp.company.com
  port: 587
  user: alerts@company.com
  password: ${SMTP_PASSWORD}

recipients:
  critical: [devops@company.com, oncall@company.com]
  warning: [data-team@company.com]
  info: [data-team@company.com]
```

### 8.2 Slack Integration

```bash
# Send Slack alert
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Pipeline failed!"}' \
  $SLACK_WEBHOOK_URL
```

---

*Document version: 1.0*
*Last updated: 2025-02-17*
*Owner: Pierre Durand (DevOps)*
