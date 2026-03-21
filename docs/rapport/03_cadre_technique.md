# Cadre Technique d'Exploitation (C3)

## 1. Analyse fonctionnelle

### 1.1 Que fait le système ?
Le système **Portfolio Optimization Pipeline** :
1. Collecte automatiquement les données OHLCV depuis Binance
2. Stocke les données dans un Data Lake (Parquet)
3. Transforme les données en métriques financières
4. Expose les données via un Data Warehouse (DuckDB)
5. Calcule l'allocation optimale de portefeuille
6. Met à disposition les résultats via API REST

### 1.2 Contraintes métiers
| Contrainte | Impact sur l'architecture |
|------------|---------------------------|
| Budget limité | Solutions open-source uniquement |
| Pas d'infrastructure cloud | Déploiement local / Docker |
| Équipe réduite | Architecture simple, maintenable |
| Données publiques | Pas de chiffrement complexe |

---

## 2. Besoins non-fonctionnels

| Besoin | Exigence | Solution |
|--------|----------|----------|
| **Performance** | Traitement < 1min pour 10 symboles | DuckDB + Parquet |
| **Disponibilité** | 99% (non critique) | Docker restart policy |
| **Scalabilité** | Jusqu'à 100 symboles | Architecture pluggable |
| **Maintenabilité** | Code lisible, documenté | Python, typing, docstrings |
| **Portabilité** | Déployable partout | Docker, pas de dépendances système |

---

## 3. Représentation fonctionnelle

```
┌─────────────────────────────────────────────────────────────────┐
│                    PORTFOLIO OPTIMIZATION                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐   ┌──────────┐   ┌──────────┐   ┌──────────┐      │
│  │ INGEST   │──▶│ STORAGE  │──▶│TRANSFORM │──▶│ OPTIMIZE │      │
│  │          │   │          │   │          │   │          │      │
│  │ Binance  │   │ Parquet  │   │ Returns  │   │ Markowitz│      │
│  │ API      │   │ DuckDB   │   │ Vol/Corr │   │ Weights  │      │
│  └──────────┘   └──────────┘   └──────────┘   └──────────┘      │
│                       │                             │           │
│                       ▼                             ▼           │
│                 ┌──────────┐                  ┌──────────┐      │
│                 │   API    │◀─────────────────│  OUTPUT  │      │
│                 │ FastAPI  │                  │  JSON    │      │
│                 └──────────┘                  └──────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Représentation applicative

### 4.1 Composants logiciels

| Composant | Technologie | Rôle |
|-----------|-------------|------|
| `src/pipeline/ingest.py` | Python + httpx | Extraction API Binance |
| `src/pipeline/transform.py` | Python + pyarrow | Calculs statistiques |
| `src/pipeline/optimize.py` | Python (+ scipy) | Optimisation Markowitz |
| `src/storage/parquet.py` | pyarrow | Stockage Data Lake |
| `src/storage/duckdb.py` | DuckDB | Data Warehouse SQL |
| `src/api/main.py` | FastAPI | Exposition REST |

### 4.2 Matrice des flux applicatifs

| Source | Cible | Protocole | Données |
|--------|-------|-----------|---------|
| ingest.py | Binance | HTTPS | JSON klines |
| ingest.py | storage | Filesystem | Parquet |
| transform.py | storage | Filesystem | Parquet |
| optimize.py | storage | Filesystem | JSON |
| api | storage | In-process | Dict Python |
| Client | api | HTTP | JSON |

---

## 5. Représentation d'infrastructure

### 5.1 Architecture Docker

```
┌─────────────────────────────────────────┐
│              Docker Host                │
├─────────────────────────────────────────┤
│                                         │
│  ┌────────────────┐  ┌────────────────┐ │
│  │   api          │  │   pipeline     │ │
│  │   container    │  │   container    │ │
│  │                │  │                │ │
│  │  Port 8000     │  │  (on-demand)   │ │
│  └───────┬────────┘  └───────┬────────┘ │
│          │                   │          │
│          └─────────┬─────────┘          │
│                    │                    │
│           ┌───────▼────────┐            │
│           │  Volume: data/ │            │
│           │                │            │
│           │ raw/           │            │
│           │ processed/     │            │
│           │ output/        │            │
│           └────────────────┘            │
│                                         │
└─────────────────────────────────────────┘
```

### 5.2 Ressources requises

| Ressource | Minimum | Recommandé |
|-----------|---------|------------|
| CPU | 1 core | 2 cores |
| RAM | 512 MB | 1 GB |
| Disque | 100 MB | 1 GB |
| Réseau | Internet (Binance) | - |

---

## 6. Représentation opérationnelle

### 6.1 Cycle de vie des données

```
[Binance API]
     │
     │ Quotidien (cron/manuel)
     ▼
[Bronze: data/raw/]  ──────────▶ Rétention: 1 an
     │
     │ Après chaque ingest
     ▼
[Silver: data/processed/] ─────▶ Rétention: 1 an
     │
     │ Après chaque transform
     ▼
[Gold: data/output/] ──────────▶ Rétention: 30 jours
```

### 6.2 Monitoring

| Métrique | Outil | Seuil alerte |
|----------|-------|--------------|
| API disponibilité | Docker healthcheck | < 99% |
| Espace disque | OS monitoring | > 80% |
| Erreurs pipeline | Logs stdout | > 0 |

---

## 7. Décisions d'architecture

### 7.1 Choix techniques justifiés

| Décision | Justification |
|----------|---------------|
| **Python** | Écosystème data mature, équipe compétente |
| **Parquet** | Format columnar optimisé, compressé, standard |
| **DuckDB** | SQL sur fichiers, pas de serveur, performant |
| **FastAPI** | Moderne, async, auto-documentation OpenAPI |
| **Docker** | Portabilité, isolation, reproductibilité |
| **No pandas** | Dépendance lourde, pyarrow suffit |

### 7.2 Alternatives écartées

| Alternative | Raison du rejet |
|-------------|-----------------|
| PostgreSQL | Trop lourd pour le besoin, nécessite serveur |
| Airflow | Overkill pour un pipeline simple |
| Spark | Volume de données insuffisant |
| Cloud (AWS/GCP) | Budget, complexité |

---

## 8. Éco-responsabilité

### 8.1 Mesures adoptées
Conformément au [RGESN](https://ecoresponsable.numerique.gouv.fr/publications/referentiel-general-ecoconception/) :

| Mesure | Impact |
|--------|--------|
| Pas de cloud | Réduction empreinte datacenter |
| Docker multi-stage | Image légère (~200MB) |
| Parquet compressé | Réduction stockage 70% |
| DuckDB in-memory | Pas de serveur permanent |
| API on-demand | Pas de compute inutile |

### 8.2 Indicateurs
- Taille image Docker : < 500 MB
- Stockage données 1 an : < 100 MB
- Consommation mémoire : < 500 MB

---

## 9. Accessibilité

### 9.1 Adaptation des postes de travail
- API REST : accessible depuis tout client HTTP
- Documentation OpenAPI : navigateur standard
- Logs : format texte lisible

### 9.2 Utilisateurs finaux
- API JSON : compatible lecteurs d'écran
- Pas d'interface graphique complexe
