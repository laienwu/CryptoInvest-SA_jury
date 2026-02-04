# Incident Response Plan

## Document Control

| Item | Details |
|------|---------|
| Document ID | IRP-PORTFOLIO-001 |
| Version | 1.0 |
| Classification | Internal |
| Owner | Pierre Durand (DevOps) |
| Last Updated | 2025-02-17 |

---

## 1. Purpose & Scope

### 1.1 Purpose

This Incident Response Plan (IRP) establishes procedures for detecting, responding to, and recovering from incidents affecting the Portfolio Optimization Platform.

### 1.2 Scope

Applies to all incidents affecting:
- API service availability
- Data pipeline operations
- Data integrity and quality
- Security breaches
- Infrastructure failures

### 1.3 Objectives

1. Minimize service disruption
2. Protect data integrity
3. Maintain stakeholder communication
4. Learn from incidents to prevent recurrence

---

## 2. Incident Classification

### 2.1 Severity Levels

| Level | Name | Definition | Examples |
|-------|------|------------|----------|
| SEV-1 | Critical | Complete outage, data breach, security incident | API down, data corruption |
| SEV-2 | Major | Significant degradation, partial outage | Pipeline failed, high latency |
| SEV-3 | Minor | Limited impact, workaround available | Single endpoint error |
| SEV-4 | Low | Minimal impact, cosmetic issues | UI glitch, log warning |

### 2.2 Classification Matrix

| Impact | All Users | Some Users | Single User |
|--------|-----------|------------|-------------|
| **Service Down** | SEV-1 | SEV-2 | SEV-3 |
| **Degraded** | SEV-2 | SEV-3 | SEV-4 |
| **Inconvenience** | SEV-3 | SEV-4 | SEV-4 |

### 2.3 Response Times

| Severity | Detection | Response | Resolution | Communication |
|----------|-----------|----------|------------|---------------|
| SEV-1 | 5 min | 15 min | 4 hours | Every 30 min |
| SEV-2 | 15 min | 1 hour | 8 hours | Every 2 hours |
| SEV-3 | 1 hour | 4 hours | 24 hours | Daily |
| SEV-4 | 24 hours | Best effort | Best effort | On resolution |

---

## 3. Incident Response Team

### 3.1 Roles & Responsibilities

| Role | Responsibility | Primary | Backup |
|------|----------------|---------|--------|
| Incident Commander | Overall coordination | Pierre Durand | [Your Name] |
| Technical Lead | Investigation & fix | [Your Name] | Sophie Bernard |
| Communications | Stakeholder updates | Lucas Petit | Marie Dupont |
| Scribe | Documentation | Assigned at runtime | - |

### 3.2 Contact Information

| Role | Name | Phone | Email |
|------|------|-------|-------|
| On-Call Primary | Rotating | +33 X XX XX XX XX | oncall@company.com |
| DevOps Lead | Pierre Durand | +33 X XX XX XX XX | pierre@company.com |
| Data Engineer | [Your Name] | +33 X XX XX XX XX | data@company.com |
| CTO (Escalation) | François Martin | +33 X XX XX XX XX | francois@company.com |

### 3.3 Escalation Path

```
┌─────────────────────────────────────────────────────────────────┐
│                      ESCALATION TIMELINE                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  0 min      On-Call Engineer alerted                            │
│     │                                                            │
│     │       ┌─ SEV-1: Immediate escalation to all               │
│     │       │                                                    │
│  15 min     ├─ SEV-2: Escalate to Tech Lead                     │
│     │       │                                                    │
│     │       └─ SEV-3/4: Continue solo                           │
│     │                                                            │
│  30 min     No progress → Escalate to next level                │
│     │                                                            │
│  1 hour     SEV-1/2: DevOps Lead joins                          │
│     │                                                            │
│  2 hours    SEV-1: CTO notified                                 │
│     │                                                            │
│  4 hours    SEV-1: All hands, business notified                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Incident Response Phases

### 4.1 Phase 1: Detection

**Objective:** Identify that an incident is occurring

**Sources:**
- Automated monitoring alerts
- Health check failures
- User reports
- Manual observation

**Actions:**
1. Acknowledge alert
2. Verify incident is real (not false positive)
3. Gather initial information
4. Classify severity

**Detection Checklist:**
```
☐ Alert received/incident reported
☐ Verified incident is genuine
☐ Initial scope assessed
☐ Severity classified
☐ Incident ticket created
```

### 4.2 Phase 2: Triage

**Objective:** Assess impact and mobilize response

**Actions:**
1. Create incident channel (Slack: #incident-YYYY-MM-DD)
2. Assign Incident Commander
3. Page additional responders if needed
4. Begin impact assessment

**Triage Checklist:**
```
☐ Incident Commander assigned
☐ Communication channel created
☐ Initial impact assessment complete
☐ Stakeholders notified (per severity)
☐ Response team assembled
```

### 4.3 Phase 3: Containment

**Objective:** Prevent further damage

**Actions:**
1. Isolate affected components
2. Preserve evidence (logs, state)
3. Implement temporary workarounds
4. Prevent incident spread

**Containment Strategies:**

| Incident Type | Containment Action |
|---------------|-------------------|
| API outage | Restart container, failover |
| Data corruption | Stop pipeline, quarantine data |
| Security breach | Revoke access, isolate system |
| Performance issue | Scale resources, enable caching |

### 4.4 Phase 4: Investigation

**Objective:** Identify root cause

**Actions:**
1. Gather logs and metrics
2. Timeline reconstruction
3. Hypothesis testing
4. Root cause identification

**Investigation Commands:**
```bash
# Gather logs
docker compose logs --since="1h" > incident_logs.txt

# Check recent changes
git log --oneline -20

# Check system state
docker compose ps
docker stats --no-stream

# Check data state
ls -la data/raw/klines/
ls -la data/output/
```

### 4.5 Phase 5: Resolution

**Objective:** Restore normal service

**Actions:**
1. Implement fix
2. Verify fix in staging (if available)
3. Deploy to production
4. Verify service restored
5. Monitor for recurrence

**Resolution Checklist:**
```
☐ Fix identified
☐ Fix tested
☐ Fix deployed
☐ Service verified operational
☐ Monitoring shows normal
☐ Stakeholders notified of resolution
```

### 4.6 Phase 6: Recovery

**Objective:** Return to full normal operations

**Actions:**
1. Remove temporary workarounds
2. Verify all services operational
3. Catch up on missed operations (pipeline backfill)
4. Confirm data integrity

**Recovery Tasks:**
```bash
# Backfill missed pipeline runs
docker compose exec airflow-webserver airflow dags backfill \
  portfolio_optimization \
  --start-date 2025-01-15 \
  --end-date 2025-01-16

# Verify data integrity
docker compose exec api python -c "
from src.storage.duckdb import DuckDBStorage
db = DuckDBStorage()
print(db.query('SELECT COUNT(*) FROM fact_prices'))
"
```

### 4.7 Phase 7: Post-Incident

**Objective:** Learn and improve

**Actions:**
1. Schedule post-mortem (within 48 hours)
2. Document timeline and actions
3. Identify improvements
4. Track action items
5. Share learnings

---

## 5. Communication Templates

### 5.1 Initial Notification (SEV-1/2)

```
Subject: [INCIDENT] Portfolio Platform - {Brief Description}

Severity: SEV-{X}
Status: Investigating

Impact:
- {Description of user/service impact}

Timeline:
- {Time} - Incident detected
- {Time} - Investigation started

Current Actions:
- {What is being done}

Next Update: {Time}

Incident Commander: {Name}
```

### 5.2 Status Update

```
Subject: [UPDATE] Portfolio Platform Incident - {Time}

Status: {Investigating/Identified/Fixing/Resolved}

Progress:
- {What we've learned}
- {What we've done}

Current Impact:
- {Updated impact assessment}

Next Steps:
- {Planned actions}

ETA: {If known, otherwise "TBD"}

Next Update: {Time}
```

### 5.3 Resolution Notification

```
Subject: [RESOLVED] Portfolio Platform Incident

Status: Resolved

Resolution:
- {What was the problem}
- {What was the fix}

Duration: {Start time} to {End time} ({X hours Y minutes})

Impact Summary:
- {Services affected}
- {Data affected, if any}

Follow-up:
- Post-mortem scheduled for {date/time}
- {Any ongoing monitoring}

Thank you for your patience.
```

---

## 6. Incident Runbooks

### 6.1 API Not Responding

**Symptoms:** Health check fails, users report errors

**Immediate Actions:**
```bash
# 1. Check container status
docker compose ps api

# 2. Check logs for errors
docker compose logs --tail=100 api

# 3. Restart container
docker compose restart api

# 4. If persists, recreate container
docker compose up -d --force-recreate api

# 5. Check resource constraints
docker stats api
```

**Escalate if:** Restart doesn't help, logs show unknown errors

### 6.2 Pipeline Failure

**Symptoms:** Airflow DAG shows failed, no data update

**Immediate Actions:**
```bash
# 1. Check Airflow task logs
# Go to http://localhost:8081 → DAG → Failed task → Logs

# 2. Check which task failed
docker compose exec airflow-webserver airflow tasks list portfolio_optimization

# 3. Clear and retry failed task
docker compose exec airflow-webserver airflow tasks clear \
  portfolio_optimization -t ingest_data -s 2025-01-15

# 4. If data source issue, check external APIs
curl -s "https://api.binance.com/api/v3/ping"

# 5. Manual run of failed step
docker compose exec api python -c "from src.pipeline import ingest_all_sources; ingest_all_sources()"
```

**Escalate if:** API errors, data corruption detected

### 6.3 Data Quality Issue

**Symptoms:** Unexpected values in API responses, alerts

**Immediate Actions:**
```bash
# 1. Stop further processing
# Pause Airflow DAG in UI

# 2. Identify bad data
docker compose exec api python -c "
import duckdb
conn = duckdb.connect('data/warehouse.duckdb')
print(conn.execute('''
  SELECT symbol, MIN(close), MAX(close), COUNT(*)
  FROM fact_prices
  GROUP BY symbol
''').fetchall())
"

# 3. Check source data
docker compose exec api python -c "
import pyarrow.parquet as pq
table = pq.read_table('data/raw/klines/BTCUSDT.parquet')
print(table.to_pandas().describe())
"

# 4. If bad data found, quarantine
mv data/raw/klines/BTCUSDT.parquet data/quarantine/

# 5. Re-ingest from source
docker compose exec api python -c "
from src.pipeline.ingest import fetch_klines
fetch_klines('BTCUSDT', days=7)
"
```

**Escalate if:** Data corruption source unknown, multiple symbols affected

### 6.4 Security Incident

**Symptoms:** Unauthorized access, suspicious activity

**Immediate Actions:**
```bash
# 1. IMMEDIATELY contain
docker compose stop  # Stop all services

# 2. Preserve evidence
cp -r logs/ incident_evidence/
docker compose logs > incident_evidence/docker_logs.txt
cp -r data/ incident_evidence/data_snapshot/

# 3. Revoke credentials
# Rotate all API keys, passwords

# 4. Notify security team
# Call security lead immediately

# 5. Do NOT:
# - Delete logs
# - Restart services without authorization
# - Communicate externally without approval
```

**Escalate immediately to:** CTO, Security Lead

---

## 7. Post-Incident Review

### 7.1 Post-Mortem Template

```markdown
# Post-Mortem: {Incident Title}

**Date:** {Incident Date}
**Duration:** {X hours Y minutes}
**Severity:** SEV-{X}
**Author:** {Name}
**Status:** {Draft/Final}

## Summary

{1-2 sentence summary of what happened}

## Impact

- Users affected: {number}
- Services affected: {list}
- Data affected: {yes/no, details}
- Revenue impact: {if applicable}

## Timeline

| Time (UTC) | Event |
|------------|-------|
| HH:MM | Incident started |
| HH:MM | Alert triggered |
| HH:MM | Response began |
| HH:MM | Root cause identified |
| HH:MM | Fix deployed |
| HH:MM | Service restored |

## Root Cause

{Detailed explanation of what caused the incident}

## Resolution

{What was done to fix the issue}

## What Went Well

- {Point 1}
- {Point 2}

## What Could Be Improved

- {Point 1}
- {Point 2}

## Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| {Action} | {Name} | {Date} | {Open/Done} |

## Lessons Learned

{Key takeaways for the team}
```

### 7.2 Post-Mortem Meeting

**Timing:** Within 48 hours of resolution

**Attendees:**
- Incident responders
- Team leads
- Affected stakeholders (optional)

**Agenda:**
1. Timeline review (15 min)
2. Root cause discussion (15 min)
3. What went well (10 min)
4. What to improve (10 min)
5. Action items (10 min)

**Rules:**
- Blameless culture - focus on systems, not people
- No interruptions during timeline review
- All voices heard
- Concrete action items with owners

---

## 8. Training & Testing

### 8.1 Training Requirements

| Role | Training | Frequency |
|------|----------|-----------|
| All engineers | IRP overview | On join, annually |
| On-call | Incident command | Quarterly |
| Leads | Communication | Annually |

### 8.2 Incident Drills

| Drill Type | Frequency | Scope |
|------------|-----------|-------|
| Tabletop exercise | Quarterly | Team discussion |
| Runbook test | Monthly | Execute runbooks |
| Full drill | Annually | Simulated incident |

### 8.3 Drill Scenarios

1. **API Outage:** Container crashes, needs restart
2. **Pipeline Failure:** Binance API returns errors
3. **Data Corruption:** Bad data in Gold zone
4. **Security:** Unauthorized API access detected

---

## 9. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-02-17 | Pierre Durand | Initial release |

---

*This plan is reviewed and updated quarterly.*
*Last drill conducted: N/A (new plan)*
*Next scheduled drill: 2025-03-15*
