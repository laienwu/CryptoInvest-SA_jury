# RACI Matrix - Portfolio Optimization Project

## Team Members

| Role | Name | Department |
|------|------|------------|
| **PO** | Product Owner | Business |
| **BA** | Business Analyst | Business |
| **DE** | Data Engineer | Development |
| **DA** | Data Analyst | Development |
| **DO** | DevOps Engineer | IT Operations |
| **SM** | Scrum Master | Project Management |

---

## RACI Legend

| Letter | Meaning | Description |
|--------|---------|-------------|
| **R** | Responsible | Does the work |
| **A** | Accountable | Final decision maker, only one per task |
| **C** | Consulted | Provides input before decision |
| **I** | Informed | Notified after decision |

---

## Project Phases

### Phase 1: Initiation & Planning

| Activity | PO | BA | DE | DA | DO | SM |
|----------|----|----|----|----|----|----|
| Define business requirements | A | R | C | C | I | I |
| Stakeholder interviews | C | R | I | I | I | I |
| Project charter approval | A | R | I | I | I | C |
| Technical feasibility study | C | I | R | C | C | I |
| Resource allocation | A | I | C | C | C | R |
| Sprint planning | C | C | R | R | R | A |

### Phase 2: Data Collection (Bloc 2)

| Activity | PO | BA | DE | DA | DO | SM |
|----------|----|----|----|----|----|----|
| API integration (Binance) | I | I | R | C | I | I |
| Multi-source ingestion | I | C | R | C | I | I |
| Data quality rules | C | R | A | C | I | I |
| Storage architecture | I | I | A | C | C | I |
| Database creation (MERISE) | I | C | R | C | I | I |
| REST API development | I | C | R | I | C | I |

### Phase 3: Data Warehouse (Bloc 3)

| Activity | PO | BA | DE | DA | DO | SM |
|----------|----|----|----|----|----|----|
| Star schema modeling | I | C | R | A | I | I |
| DuckDB implementation | I | I | R | C | I | I |
| ETL pipeline development | I | I | R | C | C | I |
| Airflow DAG creation | I | I | R | I | C | I |
| SCD implementation | I | I | R | C | I | I |
| DWH testing | I | C | R | R | I | I |

### Phase 4: Data Lake (Bloc 4)

| Activity | PO | BA | DE | DA | DO | SM |
|----------|----|----|----|----|----|----|
| Lake architecture design | I | C | A | C | C | I |
| Docker infrastructure | I | I | C | I | R | I |
| Data catalog creation | I | C | R | A | I | I |
| RGPD compliance | A | R | C | C | C | I |
| Governance rules | A | R | C | C | C | I |

### Phase 5: Deployment & Operations

| Activity | PO | BA | DE | DA | DO | SM |
|----------|----|----|----|----|----|----|
| Environment setup | I | I | C | I | R | I |
| Deployment procedures | I | I | C | I | A | I |
| Monitoring setup | I | I | C | I | R | I |
| SLA definition | A | C | C | I | R | I |
| Documentation review | C | C | R | R | R | A |
| User training | C | R | C | C | I | I |

### Phase 6: Project Closure

| Activity | PO | BA | DE | DA | DO | SM |
|----------|----|----|----|----|----|----|
| Final demo | A | R | R | R | R | C |
| Retrospective | C | C | R | R | R | A |
| Knowledge transfer | I | C | R | R | R | I |
| Project sign-off | A | C | I | I | I | R |

---

## Communication Matrix

| Stakeholder | Communication Type | Frequency | Owner |
|-------------|-------------------|-----------|-------|
| Product Owner | Sprint Review | Bi-weekly | SM |
| Business Analysts | Requirements Review | Weekly | BA |
| Development Team | Daily Standup | Daily | SM |
| IT Operations | Deployment Planning | Per release | DO |
| All Stakeholders | Status Report | Weekly | SM |
| Management | Steering Committee | Monthly | PO |

---

## Escalation Path

```
Level 1: Team Member → Scrum Master
    ↓
Level 2: Scrum Master → Product Owner
    ↓
Level 3: Product Owner → Steering Committee
    ↓
Level 4: Steering Committee → Executive Sponsor
```

---

## Approval Matrix

| Decision Type | Approver | Backup |
|---------------|----------|--------|
| Scope change | Product Owner | Steering Committee |
| Technical architecture | Data Engineer | Tech Lead |
| Budget allocation | Product Owner | Finance |
| Go-live | Product Owner + DevOps | Steering Committee |
| Security exception | IT Security | CTO |
