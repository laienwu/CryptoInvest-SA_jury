# Veille Technologique et Réglementaire (C4)

## 1. Organisation de la veille

### 1.1 Thématiques suivies
| Thématique | Pertinence projet |
|------------|-------------------|
| Data Engineering | Architecture, ETL, stockage |
| Python ecosystem | Dépendances, nouvelles versions |
| DuckDB | Évolutions, bonnes pratiques |
| RGPD / Data governance | Conformité réglementaire |
| Crypto / Finance | Contexte métier |

### 1.2 Planning veille
- **Fréquence** : 1h hebdomadaire (vendredi matin)
- **Durée** : 30 min lecture + 30 min synthèse

### 1.3 Outils utilisés
| Outil | Usage |
|-------|-------|
| Feedly | Agrégation flux RSS |
| GitHub Releases | Suivi versions DuckDB, FastAPI |
| Reddit r/dataengineering | Tendances communauté |
| Hacker News | Actualités tech |

---

## 2. Sources qualifiées

### 2.1 Critères de fiabilité
✅ Auteur identifié et compétent
✅ Date de publication récente
✅ Sources citées
✅ Site structuré et accessible
✅ Information confirmable ailleurs

### 2.2 Sources retenues

| Source | Type | Fiabilité | URL |
|--------|------|-----------|-----|
| DuckDB Blog | Officiel | ⭐⭐⭐⭐⭐ | duckdb.org/news |
| FastAPI Docs | Officiel | ⭐⭐⭐⭐⭐ | fastapi.tiangolo.com |
| Apache Arrow Blog | Officiel | ⭐⭐⭐⭐⭐ | arrow.apache.org/blog |
| CNIL | Réglementaire | ⭐⭐⭐⭐⭐ | cnil.fr |
| Data Engineering Weekly | Newsletter | ⭐⭐⭐⭐ | dataengineeringweekly.com |

---

## 3. Synthèses de veille

### 3.1 DuckDB - Évolution majeure (Janvier 2024)

**Source** : DuckDB Blog
**Date** : 2024-01

**Résumé** :
DuckDB 0.10 introduit des améliorations significatives :
- Performance accrue sur les fichiers Parquet (+30%)
- Meilleure gestion mémoire pour gros volumes
- Support natif des types Arrow

**Impact projet** :
- ✅ Confirme le choix de DuckDB
- ✅ Lecture Parquet optimisée = pipeline plus rapide
- 📝 Action : Mettre à jour vers dernière version

---

### 3.2 FastAPI - Bonnes pratiques API REST (2024)

**Source** : FastAPI Documentation
**Date** : 2024

**Résumé** :
Recommandations pour APIs production :
- Utiliser Pydantic pour validation
- Documenter avec OpenAPI automatique
- Gérer les erreurs avec HTTPException
- Ajouter healthcheck endpoint

**Impact projet** :
- ✅ Endpoint `/` healthcheck implémenté
- ✅ OpenAPI auto-généré sur `/docs`
- 📝 Action : Ajouter validation Pydantic (future)

---

### 3.3 Parquet vs autres formats (2024)

**Source** : Apache Arrow Blog
**Date** : 2024

**Résumé** :
Comparaison formats de stockage :
| Format | Compression | Lecture | Écriture |
|--------|-------------|---------|----------|
| Parquet | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |
| CSV | ⭐ | ⭐⭐ | ⭐⭐⭐⭐⭐ |
| JSON | ⭐⭐ | ⭐⭐ | ⭐⭐⭐⭐ |
| ORC | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ |

**Impact projet** :
- ✅ Parquet = bon choix pour analytics
- ✅ Compression snappy = équilibre taille/vitesse

---

### 3.4 RGPD - Données financières (2024)

**Source** : CNIL
**Date** : 2024

**Résumé** :
Les données de marché crypto (prix, volumes) sont des **données publiques** :
- Pas de données personnelles (PII)
- Pas de consentement requis
- Pas de registre des traitements obligatoire

⚠️ Si le système traitait des données utilisateurs (portefeuilles personnels), le RGPD s'appliquerait pleinement.

**Impact projet** :
- ✅ Données Binance = publiques
- ✅ Pas de conformité RGPD complexe requise
- 📝 Documenter cette analyse (cf. rapport RGPD)

---

### 3.5 UV - Nouveau gestionnaire Python (2024)

**Source** : Astral (créateurs de Ruff)
**Date** : 2024

**Résumé** :
`uv` est un gestionnaire de dépendances Python ultra-rapide :
- 10-100x plus rapide que pip
- Remplace pip, pip-tools, virtualenv
- Compatible pyproject.toml

**Impact projet** :
- ✅ Adopté pour le projet
- ✅ Lockfile `uv.lock` pour reproductibilité
- ✅ Intégré au Dockerfile

---

## 4. Recommandations issues de la veille

### 4.1 Actions immédiates
| Action | Priorité | Status |
|--------|----------|--------|
| Utiliser DuckDB dernière version | Haute | ✅ Done |
| Documenter conformité RGPD | Moyenne | ✅ Done |
| Ajouter healthcheck API | Basse | ✅ Done |

### 4.2 Actions futures
| Action | Priorité | Échéance |
|--------|----------|----------|
| Validation Pydantic sur API | Basse | v2.0 |
| Monitoring Prometheus | Basse | v2.0 |
| Tests de charge | Basse | v2.0 |

---

## 5. Partage de la veille

### 5.1 Format de diffusion
- Synthèses intégrées au rapport projet
- Notes techniques dans `docs/`
- Commits Git avec références sources

### 5.2 Accessibilité
- Documents en Markdown (texte structuré)
- Compatible lecteurs d'écran
- Pas d'images sans alt-text
