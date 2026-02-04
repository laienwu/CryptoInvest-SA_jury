# Security Checklist

## Overview

This document provides security guidelines and checklists for the Portfolio Optimization Platform. All items should be reviewed before production deployment.

---

## 1. Pre-Deployment Checklist

### 1.1 Application Security

| Item | Status | Notes |
|------|--------|-------|
| No hardcoded credentials | ☐ | Check all source files |
| Environment variables for secrets | ☐ | Use .env file (not in git) |
| Input validation on all endpoints | ☐ | Pydantic models enforce types |
| SQL injection prevention | ☐ | Parameterized queries only |
| XSS prevention | ☐ | API returns JSON only |
| CORS configuration | ☐ | Restrict to known origins |
| Rate limiting enabled | ☐ | Prevent DoS attacks |
| Error messages sanitized | ☐ | No stack traces in production |

### 1.2 Infrastructure Security

| Item | Status | Notes |
|------|--------|-------|
| Docker images from trusted sources | ☐ | Official images only |
| Containers run as non-root | ☐ | USER directive in Dockerfile |
| Network isolation configured | ☐ | Docker network segmentation |
| Volumes have restricted permissions | ☐ | 755 for dirs, 644 for files |
| Ports exposed only as needed | ☐ | Minimize attack surface |
| TLS/HTTPS enabled | ☐ | For production only |
| Firewall rules configured | ☐ | Block unnecessary traffic |

### 1.3 Data Security

| Item | Status | Notes |
|------|--------|-------|
| No PII in logs | ☐ | Scrub sensitive data |
| Data at rest encryption | ☐ | Volume encryption |
| Data in transit encryption | ☐ | HTTPS for API |
| Backup encryption | ☐ | Encrypted backup storage |
| Data retention policy defined | ☐ | See data governance docs |
| RGPD compliance verified | ☐ | No personal data processed |

---

## 2. Credential Management

### 2.1 Required Secrets

| Secret | Storage | Rotation |
|--------|---------|----------|
| Binance API key | Environment variable | Annually |
| PostgreSQL password | Docker secret / .env | Quarterly |
| Airflow admin password | Docker secret / .env | Quarterly |
| SMTP credentials (alerts) | Docker secret / .env | Annually |

### 2.2 Secret Storage Guidelines

**DO:**
```bash
# Use environment variables
export BINANCE_API_KEY="your-key-here"

# Use Docker secrets (compose)
secrets:
  binance_api_key:
    file: ./secrets/binance_api_key.txt

# Use .env file (local development)
# .env (gitignored)
BINANCE_API_KEY=your-key-here
```

**DON'T:**
```python
# NEVER hardcode secrets
API_KEY = "abc123"  # BAD!

# NEVER commit secrets to git
# .env should be in .gitignore
```

### 2.3 .gitignore Requirements

```gitignore
# Secrets - NEVER commit
.env
.env.*
secrets/
*.key
*.pem
credentials.json

# Local config with secrets
config.local.toml
```

---

## 3. API Security

### 3.1 Current State (MVP)

| Control | Status | Notes |
|---------|--------|-------|
| Authentication | ❌ Not implemented | Internal use only |
| Authorization | ❌ Not implemented | Internal use only |
| Rate limiting | ❌ Not implemented | Post-MVP |
| HTTPS | ❌ Not implemented | Localhost only |
| API keys | ❌ Not implemented | Post-MVP |

### 3.2 Production Requirements

Before external exposure, implement:

```python
# Example: API key authentication
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != os.getenv("API_KEY"):
        raise HTTPException(status_code=403, detail="Invalid API key")
    return api_key

@app.get("/portfolio", dependencies=[Depends(verify_api_key)])
def get_portfolio():
    ...
```

### 3.3 CORS Configuration

```python
from fastapi.middleware.cors import CORSMiddleware

# Production: restrict origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dashboard.company.com"],  # Specific origins
    allow_methods=["GET"],  # Read-only API
    allow_headers=["X-API-Key"],
)
```

### 3.4 Rate Limiting

```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.get("/portfolio")
@limiter.limit("100/minute")
def get_portfolio():
    ...
```

---

## 4. Container Security

### 4.1 Dockerfile Best Practices

```dockerfile
# Use specific version tags (not :latest)
FROM python:3.11-slim

# Run as non-root user
RUN useradd -m appuser
USER appuser

# Don't install unnecessary packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy only necessary files
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser pyproject.toml ./

# Use multi-stage builds to reduce image size
```

### 4.2 Docker Compose Security

```yaml
services:
  api:
    # Don't run as root
    user: "1000:1000"

    # Read-only filesystem where possible
    read_only: true
    tmpfs:
      - /tmp

    # Drop all capabilities, add only needed
    cap_drop:
      - ALL

    # Limit resources
    deploy:
      resources:
        limits:
          memory: 512M
          cpus: '1.0'

    # Security options
    security_opt:
      - no-new-privileges:true
```

### 4.3 Image Scanning

```bash
# Scan image for vulnerabilities
docker scan portfolio-api:latest

# Or use Trivy
trivy image portfolio-api:latest
```

---

## 5. Network Security

### 5.1 Network Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         EXTERNAL                                 │
│                      (Internet/VPN)                              │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                    [Firewall/LB]
                           │
                    [HTTPS :443]
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                          │         DMZ NETWORK                   │
│                          ▼                                       │
│                  ┌───────────────┐                              │
│                  │   API :8000   │                              │
│                  └───────┬───────┘                              │
│                          │                                       │
└──────────────────────────┼──────────────────────────────────────┘
                           │
┌──────────────────────────┼──────────────────────────────────────┐
│                          │       INTERNAL NETWORK                │
│                          ▼                                       │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐       │
│  │   Airflow     │  │   PostgreSQL  │  │  Data Lake    │       │
│  │    :8081      │  │    :5432      │  │  (volumes)    │       │
│  └───────────────┘  └───────────────┘  └───────────────┘       │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Firewall Rules

| Source | Destination | Port | Protocol | Action |
|--------|-------------|------|----------|--------|
| Internet | API | 443 | HTTPS | Allow |
| Internal | Airflow | 8081 | HTTP | Allow |
| API | PostgreSQL | 5432 | TCP | Allow |
| * | * | * | * | Deny |

### 5.3 Docker Network Isolation

```yaml
networks:
  frontend:
    driver: bridge
  backend:
    driver: bridge
    internal: true  # No external access

services:
  api:
    networks:
      - frontend
      - backend

  postgres:
    networks:
      - backend  # Only internal access
```

---

## 6. Monitoring & Audit

### 6.1 Security Logging

| Event | Log Level | Retention |
|-------|-----------|-----------|
| Authentication attempts | INFO | 90 days |
| Failed authentication | WARNING | 1 year |
| API errors (4xx, 5xx) | WARNING | 90 days |
| Configuration changes | INFO | 1 year |
| Admin actions | INFO | 1 year |

### 6.2 Audit Trail

```python
# Log all API requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start

    logger.info(
        "API request",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration * 1000,
            "client_ip": request.client.host,
            "user_agent": request.headers.get("user-agent"),
        }
    )
    return response
```

### 6.3 Security Alerts

| Alert | Condition | Action |
|-------|-----------|--------|
| Brute force | > 10 failed auth/min | Block IP, notify |
| Unusual traffic | > 1000 req/min | Rate limit, investigate |
| Error spike | > 10% error rate | Investigate |
| Config change | Any | Audit, notify |

---

## 7. Vulnerability Management

### 7.1 Dependency Scanning

```bash
# Check Python dependencies
pip-audit

# Or with safety
safety check

# Update dependencies
pip install --upgrade -r requirements.txt
```

### 7.2 Update Schedule

| Component | Frequency | Notes |
|-----------|-----------|-------|
| OS packages | Monthly | Security patches |
| Python deps | Monthly | Check for CVEs |
| Docker images | Monthly | Rebuild with updates |
| Framework (FastAPI) | Quarterly | Minor version updates |

### 7.3 CVE Response

| Severity | Response Time | Action |
|----------|---------------|--------|
| Critical | 24 hours | Immediate patch |
| High | 7 days | Priority patch |
| Medium | 30 days | Next release |
| Low | 90 days | Best effort |

---

## 8. Incident Response

### 8.1 Security Incident Types

| Type | Severity | Initial Response |
|------|----------|------------------|
| Data breach | Critical | Isolate, investigate, notify |
| Unauthorized access | Critical | Revoke access, investigate |
| DDoS attack | High | Enable mitigation, investigate |
| Malware detection | High | Isolate, scan, clean |
| Vulnerability discovered | Medium | Assess, patch, monitor |

### 8.2 Response Checklist

1. **Detect:** Identify the incident
2. **Contain:** Isolate affected systems
3. **Investigate:** Determine scope and impact
4. **Eradicate:** Remove threat
5. **Recover:** Restore services
6. **Learn:** Post-incident review

See `incident_response.md` for detailed procedures.

---

## 9. Compliance

### 9.1 RGPD Compliance

| Requirement | Status | Notes |
|-------------|--------|-------|
| Data inventory | ✅ | See data catalog |
| Legal basis documented | ✅ | Market data = legitimate interest |
| No personal data processed | ✅ | Only market prices |
| Data retention policy | ✅ | 90 days rolling window |
| Right to erasure | N/A | No personal data |

### 9.2 Security Standards

| Standard | Relevant Controls | Status |
|----------|-------------------|--------|
| OWASP Top 10 | All | Reviewed |
| CIS Docker Benchmark | Container security | Partial |
| SOC 2 | Access control, audit | N/A (internal) |

---

## 10. Sign-Off

| Role | Name | Date | Signature |
|------|------|------|-----------|
| DevOps | Pierre Durand | ______ | _________ |
| Security Review | Thomas Leroy | ______ | _________ |
| CTO Approval | François Martin | ______ | _________ |

---

*Last security review: 2025-02-17*
*Next scheduled review: 2025-05-17*
