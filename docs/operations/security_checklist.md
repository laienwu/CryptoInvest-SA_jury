# Liste de contrôle de sécurité

## Présentation

Ce document fournit des directives de sécurité et des listes de contrôle pour la plateforme d'optimisation de portefeuille. Tous les éléments doivent être examinés avant le déploiement en production.

---

## 1. Liste de contrôle préalable au déploiement

### 1.1 Sécurité des applications

| Article | Statut | Remarques |
|------|--------|-------|
| Aucune information d'identification codée en dur | ☐ | Vérifiez tous les fichiers sources |
| Variables d'environnement pour les secrets | ☐ | Utilisez le fichier .env (pas dans git) |
| Validation des entrées sur tous les points de terminaison | ☐ | Les modèles pydantiques appliquent les types |
| Prévention des injections SQL | ☐ | Requêtes paramétrées uniquement |
| Prévention XSS | ☐ | L'API renvoie JSON uniquement |
| Configuration CORS | ☐ | Restreindre aux origines connues |
| Limitation de débit activée | ☐ | Prévenir les attaques DoS |
| Messages d'erreur nettoyés | ☐ | Aucune trace de pile en production |

### 1.2 Sécurité de l'infrastructure

| Article | Statut | Remarques |
|------|--------|-------|
| Images Docker provenant de sources fiables | ☐ | Images officielles uniquement |
| Les conteneurs s'exécutent en tant que non-root | ☐ | Directive USER dans Dockerfile |
| Isolation du réseau configurée | ☐ | Segmentation du réseau Docker |
| Les volumes ont des autorisations restreintes | ☐ | 755 pour les répertoires, 644 pour les fichiers |
| Ports exposés uniquement en cas de besoin | ☐ | Minimiser la surface d'attaque |
| TLS/HTTPS activé | ☐ | Pour la production uniquement |
| Règles de pare-feu configurées | ☐ | Bloquer le trafic inutile |

### 1.3 Sécurité des données

| Article | Statut | Remarques |
|------|--------|-------|
| Aucune information personnelle dans les journaux | ☐ | Effacer les données sensibles |
| Cryptage des données au repos | ☐ | Chiffrement de volume |
| Chiffrement des données en transit | ☐ | HTTPS pour API |
| Cryptage de sauvegarde | ☐ | Stockage de sauvegarde crypté |
| Politique de conservation des données définie | ☐ | Voir les documents sur la gouvernance des données |
| Conformité RGPD vérifiée | ☐ | Aucune donnée personnelle traitée |

---

## 2. Gestion des informations d'identification

### 2.1 Secrets requis

| Secrets | Stockage | Rotation |
|--------|---------|----------|
| Clé API Binance | Variable d'environnement | Annuellement |
| Mot de passe PostgreSQL | Secret Docker / .env | Trimestriel |
| Mot de passe administrateur Airflow | Secret Docker / .env | Trimestriel |
| Identifiants SMTP (alertes) | Secret Docker / .env | Annuellement |

### 2.2 Directives de stockage secret

**FAIRE :**
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

**À NE PAS FAIRE :**
```python
# NEVER hardcode secrets
API_KEY = "abc123"  # BAD!

# NEVER commit secrets to git
# .env should be in .gitignore
```

### Exigences 2.3 .gitignore

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

## 3. Sécurité des API

### 3.1 État actuel (MVP)

| Contrôle | Statut | Remarques |
|---------|--------|-------|
| Authentification | ❌ Non implémenté | Usage interne uniquement |
| Autorisation | ❌ Non implémenté | Usage interne uniquement |
| Limitation du taux | ❌ Non implémenté | Post-MVP |
| HTTPS | ❌ Non implémenté | Localhost uniquement |
| Clés API | ❌ Non implémenté | Post-MVP |

### 3.2 Exigences de production

Avant l'exposition externe, mettez en œuvre :

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

### 3.3 Configuration CORS

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

### 3.4 Limitation du débit

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

## 4. Sécurité des conteneurs

### 4.1 Bonnes pratiques Dockerfile

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

### 4.2 Sécurité de Docker Compose

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

### 4.3 Numérisation d'images

```bash
# Scan image for vulnerabilities
docker scan portfolio-api:latest

# Or use Trivy
trivy image portfolio-api:latest
```

---

## 5. Sécurité du réseau

### 5.1 Architecture du réseau

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

### 5.2 Règles de pare-feu

| Source | Destination | Port | Protocole | Action |
|--------|-------------|------|----------|--------|
| Internet | API | 443 | HTTPS | Autoriser |
| Interne | Flux d'air | 8081 | HTTP | Autoriser |
| API | PostgreSQL | 5432 | TCP | Autoriser |
| * | * | * | * | Refuser |

### 5.3 Isolation du réseau Docker

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

## 6. Surveillance et audit

### 6.1 Journalisation de sécurité

| Événement | Niveau de journalisation | Rétention |
|-------|-----------|-----------|
| Tentatives d'authentification | INFOS | 90 jours |
| Échec de l'authentification | AVERTISSEMENT | 1 an |
| Erreurs API (4xx, 5xx) | AVERTISSEMENT | 90 jours |
| Modifications de configuration | INFOS | 1 an |
| Actions d'administration | INFOS | 1 an |

### 6.2 Piste d'audit

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

### 6.3 Alertes de sécurité

| Alerte | État | Action |
|-------|-----------|--------|
| Force brute | > 10 échecs d'authentification/min | Bloquer l'adresse IP, avertir |
| Trafic inhabituel | > 1000 req/min | Limite de débit, enquêter |
| Pic d'erreur | > 10 % de taux d'erreur | Enquêter |
| Changement de configuration | N'importe quel | Auditer, notifier |

---

## 7. Gestion des vulnérabilités

### 7.1 Analyse des dépendances

```bash
# Check Python dependencies
pip-audit

# Or with safety
safety check

# Update dependencies
pip install --upgrade -r requirements.txt
```

### Calendrier de mise à jour 7.2

| Composant | Fréquence | Remarques |
|-----------|-----------|-------|
| Paquets de système d'exploitation | Mensuel | Correctifs de sécurité |
| Dépôts Python | Mensuel | Rechercher les CVE |
| Images Docker | Mensuel | Reconstruire avec les mises à jour |
| Cadre (FastAPI) | Trimestriel | Mises à jour des versions mineures |

### 7.3 Réponse CVE

| Gravité | Temps de réponse | Action |
|----------|---------------|--------|
| Critique | 24 heures | Patch immédiat |
| Élevé | 7 jours | Correctif prioritaire |
| Moyen | 30 jours | Prochaine version |
| Faible | 90 jours | Meilleur effort |

---

## 8. Réponse aux incidents

### 8.1 Types d'incidents de sécurité

| Tapez | Gravité | Réponse initiale |
|------|----------|------------------|
| Violation de données | Critique | Isoler, enquêter, avertir |
| Accès non autorisé | Critique | Révoquer l'accès, enquêter |
| Attaque DDoS | Élevé | Activer l'atténuation, enquêter |
| Détection des logiciels malveillants | Élevé | Isoler, scanner, nettoyer |
| Vulnérabilité découverte | Moyen | Évaluer, corriger, surveiller |

### 8.2 Liste de contrôle de réponse

1. **Détecter :** Identifiez l'incident
2. **Contenir :** Isoler les systèmes concernés
3. **Enquête :** Déterminer la portée et l'impact
4. **Éradiquer :** Supprimer la menace
5. **Récupération :** Services de restauration
6. **En savoir :** Examen post-incident

Voir `incident_response.md` pour les procédures détaillées.

---

## 9. Conformité

### 9.1 RGPD Conformité

| Exigence | Statut | Remarques |
|-------------|--------|-------|
| Inventaire des données | ✅ | Voir le catalogue de données |
| Base juridique documentée | ✅ | Données de marché = intérêt légitime |
| Aucune donnée personnelle traitée | ✅ | Uniquement les prix du marché |
| Politique de conservation des données | ✅ | Fenêtre glissante de 90 jours |
| Droit à l'effacement | N/A | Aucune donnée personnelle |

### 9.2 Normes de sécurité

| Norme | Contrôles pertinents | Statut |
|----------|-------------------|--------|
| Top 10 de l'OWASP | Tout | Révisé |
| Référence Docker CIS | Sécurité des conteneurs | Partiel |
| SOC2 | Contrôle d'accès, audit | N/A (interne) |

---

## 10. Signature

| Rôle | Nom | Dates | Signature |
|------|------|------|-----------|
| DevOps | Pierre Durand | ______ | _________ |
| Examen de sécurité | Thomas Leroy | ______ | _________ |
| Approbation du CTO | François Martin | ______ | _________ |

---

*Dernier examen de sécurité : 2025-02-17*
*Prochain examen programmé : 2025-05-17*
