# ADR-004: FastAPI for Data Exposure

**Status:** Accepted
**Date:** 2025-01-15
**Deciders:** [Your Name] (Data Engineer), Pierre Durand (DevOps)
**Technical Story:** US-007

---

## Context

We need to expose processed data and portfolio optimization results via REST API. Requirements:

- RESTful endpoints for price data, metrics, portfolio weights
- OpenAPI documentation (for certification)
- Low latency (< 500ms response time)
- Easy deployment (Docker)
- Python ecosystem compatibility

Options considered:
1. FastAPI
2. Flask
3. Django REST Framework
4. Connexion (OpenAPI-first)
5. Litestar

---

## Decision

**We will use FastAPI as the REST API framework.**

---

## Rationale

### Comparison:

| Criterion | FastAPI | Flask | Django REST | Connexion |
|-----------|---------|-------|-------------|-----------|
| Performance | Excellent | Good | Good | Good |
| Auto documentation | Yes | No | Yes | Yes |
| Type hints | Native | Optional | Optional | Via spec |
| Learning curve | Low | Low | Medium | Medium |
| Async support | Native | Limited | Limited | Limited |
| Validation | Pydantic | Manual | Serializers | Via spec |

### Key factors:

1. **Auto-generated OpenAPI**: FastAPI generates `/docs` (Swagger UI) and `/redoc` automatically from type hints. Critical for C12 certification requirement.

2. **Performance**: ASGI-based, one of the fastest Python frameworks. Benchmarks show 2-3x faster than Flask for JSON responses.

3. **Type safety**: Native Pydantic integration validates request/response data:
   ```python
   @app.get("/portfolio", response_model=PortfolioResponse)
   def get_portfolio() -> PortfolioResponse:
       ...  # Response automatically validated
   ```

4. **Minimal code**: Less boilerplate than Flask or Django:
   ```python
   # FastAPI
   @app.get("/symbols")
   def list_symbols() -> list[str]:
       return ["BTCUSDT", "ETHUSDT"]

   # Flask equivalent
   @app.route("/symbols")
   def list_symbols():
       return jsonify(["BTCUSDT", "ETHUSDT"])
   ```

5. **Modern Python**: Uses Python 3.10+ features (type hints, async/await).

### Why not Flask:
- No auto-generated OpenAPI docs
- Manual validation required
- Sync-only by default

### Why not Django:
- Overkill for API-only project
- ORM not needed (we use DuckDB)
- Heavier deployment footprint

---

## Consequences

### Positive
- Auto-generated OpenAPI documentation
- Request/response validation via Pydantic
- Excellent performance
- Easy async support for future needs
- Modern, clean API design

### Negative
- Relatively new framework (less battle-tested than Flask)
- Pydantic v2 migration may require updates
- Team needs to learn Pydantic models

### Neutral
- Uvicorn required as ASGI server
- Async not used in MVP (sync endpoints sufficient)

---

## Compliance

| Requirement | Status |
|-------------|--------|
| C12 - REST API exposure | Full REST implementation |
| C12 - API documentation | Auto-generated OpenAPI at /docs |

---

## Implementation

### API Structure

```
src/api/
├── main.py          # FastAPI app, routes
├── models.py        # Pydantic request/response models
└── dependencies.py  # Shared dependencies (storage, config)
```

### Endpoints

| Method | Endpoint | Description | Response Model |
|--------|----------|-------------|----------------|
| GET | `/` | Health check | `{"status": "ok"}` |
| GET | `/symbols` | List symbols | `list[str]` |
| GET | `/klines/{symbol}` | Price history | `list[KlineResponse]` |
| GET | `/metrics` | Available metrics | `list[str]` |
| GET | `/portfolio` | Optimal weights | `PortfolioResponse` |

### Code Example

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Portfolio Optimization API",
    description="REST API for crypto portfolio data and optimization",
    version="1.0.0",
)

class PortfolioResponse(BaseModel):
    weights: dict[str, float]
    expected_return: float
    volatility: float
    sharpe_ratio: float

@app.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio():
    """Get optimized portfolio weights."""
    weights = load_weights()
    if not weights:
        raise HTTPException(status_code=404, detail="No portfolio computed")
    return PortfolioResponse(**weights)
```

### Docker Deployment

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Security Considerations

Current MVP: No authentication (internal use only)

Post-MVP requirements:
- API key authentication
- Rate limiting
- HTTPS in production

See ADR-005 (future) for authentication approach.

---

## References

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI vs Flask Benchmarks](https://www.techempower.com/benchmarks/)

---

*Reviewed by: Pierre Durand (DevOps)*
*Approved by: Marie Dupont (Product Owner)*
