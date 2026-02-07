# ADR-004 : FastAPI pour l'exposition des données

**Statut :** Accepté
**Date :** 2025-01-15
**Décideurs :** Laien Wu (Ingénieur de données), Pierre Durand (DevOps)
**Histoire technique :** US-007

---

## Contexte

Nous devons exposer les données traitées et les résultats d'optimisation de portefeuille via l'API REST. Exigences :

- Points de terminaison RESTful pour les données de prix, les mesures et les pondérations du portefeuille
- Documentation OpenAPI (pour certification)
- Faible latence (temps de réponse < 500 ms)
- Déploiement facile (Docker)
- Écosystème Python compatibilité

Options considérées :
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

### Comparaison :

| Critère | API rapide | Flacon | Django REST | Connexion |
|-----------|---------|-------|-------------|-----------|
| Performances | Excellent | Bon | Bon | Bon |
| Documentation automobile | Oui | Non | Oui | Oui |
| Astuces de saisie | Natif | Facultatif | Facultatif | Via la spécification |
| Courbe d'apprentissage | Faible | Faible | Moyen | Moyen |
| Prise en charge asynchrone | Natif | Limité | Limité | Limité |
| Validation | Pydantique | Manuel | Sérialiseurs | Via spec |

### Facteurs clés :

1. **OpenAPI généré automatiquement** : FastAPI génère automatiquement `/docs` (interface utilisateur Swagger) et `/redoc` à partir d'indices de type. Critique pour les exigences de certification C12.

2. **Performances** : basé sur ASGI, l'un des frameworks Python les plus rapides. Les benchmarks s'avèrent 2 à 3 fois plus rapides que Flask pour les réponses JSON.

3. **Sécurité des types** : l'intégration native de Pydantic valide les données de requête/réponse :
   ```python
   @app.get("/portfolio", response_model=PortfolioResponse)
   def get_portfolio() -> PortfolioResponse:
       ...  # Response automatically validated
   ```

4. **Code minimal** : Moins passe-partout que Flask ou Django :
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

5. **Python moderne** : utilise les fonctionnalités de Python 3.10+ (tapez des astuces, async/await).

### Pourquoi pas Flask :
- Aucun document OpenAPI généré automatiquement
- Validation manuelle requise
- Synchronisation uniquement par default

### Pourquoi pas Django :
- Overkill pour un projet API uniquement
- ORM non nécessaire (nous utilisons DuckDB)
- Déploiement plus lourd empreinte

---

## Conséquences

### Positif[
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
| C12 -Documentation API | OpenAPI générée automatiquement dans /docs |

---

## Implémentation

### Structure de l'API

```
src/api/
├── main.py          # FastAPI app, routes
├── models.py        # Pydantic request/response models
└── dependencies.py  # Shared dependencies (storage, config)
```

### Points de terminaison

| Méthode | Point de terminaison | Descriptif | Modèle de réponse |
|--------|----------|-------------|----------------|
| OBTENIR | `/` | Bilan de santé | `{"status": "ok"}` |
| OBTENIR | `/symbols` | Liste des symboles | `list[str]` |
| OBTENIR | `/klines/{symbol}` | Historique des prix | `list[KlineResponse]` |
| OBTENIR | `/metrics` | Métriques disponibles | `list[str]` |
| OBTENIR | `/portfolio` | Poids optimaux | `PortfolioResponse` |

### Exemple de code

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

### Déploiement de Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install -e .
EXPOSE 8000
CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

## Considérations de sécurité

MVP actuel : aucune authentification (usage interne uniquement)

Exigences post-MVP :
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

*Révisé par : Pierre Durand (DevOps)*
*Approuvé par : Marie Dupont (Product Owner)*

