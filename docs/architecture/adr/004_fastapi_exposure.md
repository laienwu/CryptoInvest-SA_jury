# ADR-004 : FastAPI pour l'exposition des données

**Statut :** Accepté
**Date :** 2025-01-15
**Décideurs :** Laien Wu (Ingénieur de données), Pierre Durand (DevOps)
**Histoire technique :** US-007

---

## Contexte

Nous devons exposer les données traitées et les résultats d'optimisation de portefeuille via l'API REST. Exigences :

- Points de terminaison RESTful pour les données de prix, les mesures et les pondérations du portefeuille
- Documentation OpenAPI (pour certification)
- Faible latence (temps de réponse < 500 ms)
- Déploiement facile (Docker)
- Écosystème Python compatibilité

Options considérées :
1. FastAPI
2. Flacon
3. Framework REST Django
4. Connexion (OpenAPI-first)
5. Litestar

---

## Décision

**Nous utiliserons FastAPI comme API REST framework.**

---

## Justification

### Comparaison :

| Critère | API rapide | Flacon | Django REST | Connexion |
|-----------|---------|-------|-------------|-----------|
| Performances | Excellent | Bon | Bon | Bon |
| Documentation automobile | Oui | Non | Oui | Oui |
| Astuces de saisie | Natif | Facultatif | Facultatif | Via la spécification |
| Courbe d'apprentissage | Faible | Faible | Moyen | Moyen |
| Prise en charge asynchrone | Natif | Limité | Limité | Limité |
| Validation | Pydantique | Manuel | Sérialiseurs | Via spec |

### Facteurs clés :

1. **OpenAPI généré automatiquement** : FastAPI génère automatiquement `/docs` (interface utilisateur Swagger) et `/redoc` à partir d'indices de type. Critique pour les exigences de certification C12.

2. **Performances** : basé sur ASGI, l'un des frameworks Python les plus rapides. Les benchmarks s'avèrent 2 à 3 fois plus rapides que Flask pour les réponses JSON.

3. **Sécurité des types** : l'intégration native de Pydantic valide les données de requête/réponse :
   ```python
   @app.get("/portfolio", response_model=PortfolioResponse)
   def get_portfolio() -> PortfolioResponse:
       ...  # Response automatically validated
   ```

4. **Code minimal** : Moins passe-partout que Flask ou Django :
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

5. **Python moderne** : utilise les fonctionnalités de Python 3.10+ (tapez des astuces, async/await).

### Pourquoi pas Flask :
- Aucun document OpenAPI généré automatiquement
- Validation manuelle requise
- Synchronisation uniquement par default

### Pourquoi pas Django :
- Overkill pour un projet API uniquement
- ORM non nécessaire (nous utilisons DuckDB)
- Déploiement plus lourd empreinte

---

## Conséquences

### Positif
- Documentation OpenAPI générée automatiquement
- Validation de demande/réponse via Pydantic
- Excellentes performances
- Prise en charge asynchrone facile pour les besoins futurs
- Conception d'API moderne et propre

### Négatif
- Framework relativement nouveau (moins testé au combat que Flask)
- Pydantic La migration v2 peut nécessiter des mises à jour
- L'équipe doit apprendre les modèles Pydantic

### Neutre
- Uvicorn requis comme serveur ASGI
- Async non utilisé dans MVP (points de terminaison de synchronisation suffisant)

---

## Conformité

| Exigence | Statut |
|-------------|--------|
| C12 - Exposition à l'API REST | Implémentation REST complète |
| C12 - Documentation API | OpenAPI générée automatiquement dans /docs |

---

## Implémentation

### Structure de l'API

```
src/api/
├── main.py          # FastAPI app, routes, Depends() injection
├── schemas.py       # Pydantic response models (46 schemas)
├── cache.py         # Redis cache (TTL 300s, fallback gracieux)
└── metrics.py       # Métriques Prometheus custom (pipeline_last_run, records_ingested, portfolio_sharpe)
```

### Injection de dépendances

Le stockage est injecté via `Depends()` pour découpler les endpoints du backend :

```python
from fastapi import Depends
from src.storage import get_storage
from src.storage.base import Storage

def get_storage_dep() -> Storage:
    return get_storage()

@app.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(storage: Storage = Depends(get_storage_dep)):
    data = storage.load_output("portfolio")
    ...
```

### Cache Redis

Le module `src/api/cache.py` fournit un cache optionnel avec fallback gracieux :

- TTL configurable (300 secondes par défaut)
- Quand Redis est indisponible, l'API fonctionne normalement sans cache
- Contrôlé par la variable d'environnement `REDIS_URL`

### Métriques Prometheus

Le module `src/api/metrics.py` expose des métriques métier custom :

- `pipeline_last_run_timestamp` (Gauge) : timestamp de la dernière exécution
- `records_ingested_total` (Counter) : nombre de records ingérés par source
- `portfolio_sharpe_ratio` (Gauge) : ratio de Sharpe du portefeuille optimal
- Endpoint : `GET /prom/metrics`

### Points de terminaison

| Méthode | Point de terminaison | Description |
|---------|----------------------|-------------|
| GET | `/` | Bilan de santé |
| GET | `/symbols` | Liste des symboles |
| GET | `/klines/{symbol}` | Historique des prix |
| GET | `/portfolio` | Poids optimaux (Max Sharpe) |
| GET | `/portfolio/frontier` | Frontière efficiente |
| GET | `/portfolio/backtest` | Backtest walk-forward |
| GET | `/portfolio/trad` | Portefeuille traditionnel |
| GET | `/portfolio/hrp` | HRP allocation |
| GET | `/portfolio/black-litterman` | Black-Litterman |
| GET | `/portfolio/compare-strategies` | Comparaison 6 stratégies |
| GET | `/portfolio/monte-carlo` | Simulation Monte Carlo |
| GET | `/portfolio/stress-test` | Stress testing |
| GET | `/prices/live` | Prix temps réel |
| GET | `/prom/metrics` | Métriques Prometheus |
| ... | ... | **46 endpoints au total** |

### Exemple de code

```python
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from src.api.cache import RedisCache, cached_response, get_cache
from src.api.metrics import pipeline_last_run, portfolio_sharpe, records_ingested
from src.api.schemas import PortfolioResponse, HealthResponse

app = FastAPI(
    title="Portfolio Optimization API",
    description="REST API for crypto + traditional portfolio data and optimization",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(CORSMiddleware, allow_origins=["*"], ...)

# Prometheus instrumentation
Instrumentator().instrument(app).expose(app, endpoint="/prom/metrics")

@app.get("/", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok", message="Portfolio API running")

@app.get("/portfolio", response_model=PortfolioResponse)
def get_portfolio(storage: Storage = Depends(get_storage_dep)):
    """Get optimized portfolio weights (Max Sharpe)."""
    data = storage.load_output("portfolio")
    if not data:
        raise HTTPException(status_code=404, detail="No portfolio computed")
    return PortfolioResponse(**data)
```

### Déploiement Docker

L'API est conteneurisée via `Dockerfile` basé sur `python:3.13-slim` :

```dockerfile
FROM python:3.13-slim
WORKDIR /app

# Install uv + dependencies
RUN pip install "uv>=0.9,<1"
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra yfinance --extra optimize

# Copy source
COPY src/ ./src/
COPY config.toml ./

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Considérations de sécurité

MVP actuel : aucune authentification (usage interne uniquement)

Exigences post-MVP :
- Clé API authentification
- Limitation de débit
- HTTPS en production

Voir ADR-005 (à venir) pour l'approche d'authentification.

---

## Références

- [Documentation FastAPI](https://fastapi.tiangolo.com/)
- [Documentation Pydantic](https://docs.pydantic.dev/)
- [FastAPI vs Flask Benchmarks](https://www.techempower.com/benchmarks/)

---

*Révisé par : Pierre Durand (DevOps)*
*Approuvé par : Marie Dupont (Product Owner)*
