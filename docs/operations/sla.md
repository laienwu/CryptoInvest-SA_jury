# Service Level Agreement (SLA)

## Document Information

| Item | Details |
|------|---------|
| Document ID | SLA-PORTFOLIO-001 |
| Version | 1.0 |
| Effective Date | 2025-02-28 |
| Review Date | 2025-08-28 |
| Owner | Pierre Durand (DevOps) |
| Approver | François Martin (CTO) |

---

## 1. Service Description

### 1.1 Overview

The Portfolio Optimization Platform provides automated cryptocurrency portfolio analysis and optimization services. The platform consists of:

- **Data Pipeline**: Automated daily data collection and processing
- **REST API**: Data access and portfolio recommendations
- **Airflow Dashboard**: Pipeline monitoring and management

### 1.2 Service Hours

| Component | Availability Window |
|-----------|---------------------|
| REST API | 24/7 |
| Data Pipeline | Daily at 00:00-01:00 UTC |
| Airflow Dashboard | 24/7 (best effort) |
| Support | Business hours (09:00-18:00 CET) |

---

## 2. Service Level Objectives (SLOs)

### 2.1 Availability

| Service | Target | Measurement Period | Calculation |
|---------|--------|-------------------|-------------|
| REST API | 99.5% | Monthly | Uptime / Total time |
| Data Pipeline | 99.0% | Monthly | Successful runs / Scheduled runs |
| Airflow Dashboard | 99.0% | Monthly | Uptime / Total time |

**Exclusions from availability calculation:**
- Scheduled maintenance windows (announced 48h in advance)
- External API outages (Binance, CoinGecko)
- Force majeure events

### 2.2 Performance

| Metric | Target | Percentile |
|--------|--------|------------|
| API response time | < 200ms | p50 |
| API response time | < 500ms | p95 |
| API response time | < 1000ms | p99 |
| Pipeline execution time | < 5 minutes | p95 |

### 2.3 Data Quality

| Metric | Target |
|--------|--------|
| Data freshness | < 24 hours |
| Data completeness | > 99% (non-null values) |
| Data accuracy | Validated against source |

### 2.4 Support Response Times

| Priority | Initial Response | Resolution Target |
|----------|-----------------|-------------------|
| P1 - Critical | 15 minutes | 4 hours |
| P2 - High | 1 hour | 8 hours |
| P3 - Medium | 4 hours | 24 hours |
| P4 - Low | 24 hours | Best effort |

---

## 3. Priority Definitions

### P1 - Critical

**Definition:** Complete service outage affecting all users, data corruption, or security incident.

**Examples:**
- API returns 5xx errors for all requests
- Pipeline produces incorrect data
- Security breach detected

**Response:**
- Immediate escalation to on-call engineer
- Status page updated within 15 minutes
- All hands on deck until resolved

### P2 - High

**Definition:** Major functionality impaired, significant performance degradation, or data delays.

**Examples:**
- API response time > 2 seconds
- Pipeline execution time > 30 minutes
- Data not updated for > 24 hours

**Response:**
- Assigned to available engineer
- Status page updated if customer-facing
- Resolved within business day

### P3 - Medium

**Definition:** Minor functionality impaired, partial service degradation, non-urgent improvements.

**Examples:**
- Single endpoint returning errors
- Dashboard loading slowly
- Non-critical alert firing

**Response:**
- Added to sprint backlog
- Addressed within normal development cycle

### P4 - Low

**Definition:** Cosmetic issues, feature requests, documentation updates.

**Examples:**
- UI improvements
- Documentation gaps
- Minor configuration changes

**Response:**
- Tracked in backlog
- Addressed as capacity allows

---

## 4. Maintenance Windows

### 4.1 Scheduled Maintenance

| Type | Frequency | Duration | Notice |
|------|-----------|----------|--------|
| Security patches | As needed | < 30 min | 24 hours |
| Minor updates | Weekly | < 15 min | 48 hours |
| Major updates | Monthly | < 2 hours | 1 week |
| Infrastructure | Quarterly | < 4 hours | 2 weeks |

### 4.2 Maintenance Notification

Maintenance windows will be communicated via:
- Email to registered stakeholders
- Slack channel (#portfolio-platform)
- Status page update

### 4.3 Emergency Maintenance

In case of security vulnerability or critical bug:
- Minimum 1-hour notice when possible
- Immediate action if zero-day vulnerability
- Post-incident report within 24 hours

---

## 5. Incident Management

### 5.1 Incident Severity Matrix

| Impact → | High | Medium | Low |
|----------|------|--------|-----|
| **All users** | P1 | P2 | P3 |
| **Some users** | P2 | P3 | P4 |
| **Single user** | P3 | P4 | P4 |

### 5.2 Incident Communication

| Severity | Initial Update | Ongoing Updates | Post-Incident |
|----------|----------------|-----------------|---------------|
| P1 | 15 min | Every 30 min | Within 24h |
| P2 | 1 hour | Every 2 hours | Within 48h |
| P3 | 4 hours | Daily | Within 1 week |
| P4 | As resolved | N/A | N/A |

### 5.3 Escalation Path

```
┌─────────────────────────────────────────────────────────────────┐
│                      ESCALATION PATH                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [L1] On-Call Engineer                                          │
│        │                                                         │
│        │ 30 min                                                  │
│        ▼                                                         │
│  [L2] Data Engineering Team Lead                                │
│        │                                                         │
│        │ 1 hour                                                  │
│        ▼                                                         │
│  [L3] DevOps Manager (Pierre)                                   │
│        │                                                         │
│        │ 2 hours                                                 │
│        ▼                                                         │
│  [L4] CTO (François)                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Service Credits

### 6.1 Credit Calculation

If monthly availability falls below SLO:

| Availability | Service Credit |
|--------------|----------------|
| 99.0% - 99.5% | 10% |
| 95.0% - 99.0% | 25% |
| < 95.0% | 50% |

*Note: For internal project, credits are notional (resource allocation priority)*

### 6.2 Credit Exclusions

Credits do not apply when outage is caused by:
- User error or misconfiguration
- External dependencies (Binance API outage)
- Scheduled maintenance
- Force majeure

---

## 7. Reporting

### 7.1 Monthly Reports

Delivered by 5th of each month:
- Availability metrics (uptime %)
- Performance metrics (latency percentiles)
- Incident summary
- Maintenance log

### 7.2 Quarterly Reviews

Scheduled with stakeholders:
- SLA compliance review
- Trend analysis
- Improvement recommendations
- SLA adjustment proposals

---

## 8. Dependencies & Assumptions

### 8.1 External Dependencies

| Dependency | SLA | Fallback |
|------------|-----|----------|
| Binance API | Best effort | Cached data, manual alert |
| CoinGecko | Best effort | Fallback scraping method |
| Docker Hub | Best effort | Local image cache |
| Cloud hosting | 99.9% | N/A (hosting provider SLA) |

### 8.2 Assumptions

- Network connectivity between components is reliable
- Sufficient compute resources are allocated
- Security patches are applied within maintenance windows
- Team has adequate capacity for support

---

## 9. Agreement & Signatures

### 9.1 Service Provider

| Role | Name | Signature | Date |
|------|------|-----------|------|
| DevOps Lead | Pierre Durand | ____________ | ______ |
| Data Engineer | [Your Name] | ____________ | ______ |

### 9.2 Service Consumer

| Role | Name | Signature | Date |
|------|------|-----------|------|
| Product Owner | Marie Dupont | ____________ | ______ |
| CTO (Approver) | François Martin | ____________ | ______ |

---

## 10. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2025-02-17 | Pierre Durand | Initial release |

---

*This SLA is subject to annual review and may be updated with 30 days notice.*
