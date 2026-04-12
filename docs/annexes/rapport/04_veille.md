# Veille Technologique et Reglementaire (C4)

## 1. Organisation de la veille

### 1.1 Thematiques suivies

| Thematique | Pertinence projet |
|------------|-------------------|
| Data Engineering | Architecture, ETL, stockage, streaming |
| Python ecosystem | Dependances, nouvelles versions, tooling |
| DuckDB / OLAP | Evolutions, bonnes pratiques analytiques |
| RGPD / Data governance | Conformite reglementaire |
| Crypto / Finance | Contexte metier, nouveaux instruments |
| Streaming / Event-driven | Kafka, Redpanda, temps reel |
| Data Quality / dbt | Transforms SQL, tests integres, lineage |
| Delta Lake / Lakehouse | Transactions ACID sur fichiers |

### 1.2 Planning veille

- **Frequence** : 1h hebdomadaire (vendredi matin)
- **Duree** : 30 min lecture + 30 min synthese
- **Archivage** : Syntheses classees par date dans le rapport projet

### 1.3 Outils utilises

| Outil | Usage |
|-------|-------|
| Feedly | Agregation flux RSS (DuckDB, Arrow, Kafka, dbt) |
| GitHub Releases | Suivi versions DuckDB, FastAPI, delta-rs, dbt-duckdb |
| Reddit r/dataengineering | Tendances communaute, retours d'experience |
| Hacker News | Actualites tech generales |
| Documentation officielle | Changelogs, migration guides |

---

## 2. Sources qualifiees

### 2.1 Criteres de fiabilite

Chaque source est evaluee selon les criteres suivants, conformement au referentiel :

| Critere | Description |
|---------|-------------|
| Auteur identifie | L'auteur est nomme et ses competences sont verifiables |
| Competences reconnues | L'auteur a une expertise demontree dans le domaine |
| Notoriete | La source est reconnue dans la communaute professionnelle |
| Absence d'interets personnels | Pas de conflit d'interet commercial evident |
| Date recente | Publication de moins de 12 mois |
| Sources citees | References et liens vers des sources primaires |
| Langue correcte | Redaction professionnelle, sans erreurs majeures |
| Site structure | Navigation claire, categorisation logique |
| Accessibilite | Contenu accessible sans barriere technique majeure |
| Confirmable | Information verifiable via au moins une autre source |

### 2.2 Sources retenues

| Source | Type | Criteres valides | URL |
|--------|------|------------------|-----|
| DuckDB Blog | Officiel | 10/10 | duckdb.org/news |
| FastAPI Docs | Officiel | 10/10 | fastapi.tiangolo.com |
| Apache Arrow Blog | Officiel | 10/10 | arrow.apache.org/blog |
| CNIL | Reglementaire | 10/10 | cnil.fr |
| Delta Lake / delta-rs | Officiel | 9/10 | delta.io / delta-rs GitHub |
| dbt Documentation | Officiel | 10/10 | docs.getdbt.com |
| Redpanda Blog | Officiel | 9/10 | redpanda.com/blog |
| Data Engineering Weekly | Newsletter | 8/10 | dataengineeringweekly.com |
| Astral (uv, ruff) | Officiel | 9/10 | docs.astral.sh |

### 2.3 Sources ecartees

| Source | Raison |
|--------|--------|
| Blogs personnels non dates | Date absente, auteur non identifiable |
| Forums non moderes | Information non verifiable, biais possible |
| Tutoriels sponsorises | Conflit d'interet commercial |

---

## 3. Syntheses de veille

### 3.1 DuckDB -- Evolution majeure (Janvier 2024)

**Source** : DuckDB Blog (duckdb.org)
**Date** : 2024-01
**Auteur** : Mark Raasveldt, Hannes Muhleisen (createurs DuckDB)
**Criteres** : Auteur identifie, competences reconnues (PhD, CWI Amsterdam), source officielle

**Resume** :
DuckDB 0.10 introduit des ameliorations significatives :
- Performance accrue sur les fichiers Parquet (+30%)
- Meilleure gestion memoire pour gros volumes
- Support natif des types Arrow

**Impact projet** :
- Confirme le choix de DuckDB comme entrepot analytique (ADR-002)
- Lecture Parquet optimisee = pipeline plus rapide
- Action : Mise a jour vers derniere version -- **fait**

---

### 3.2 FastAPI -- Bonnes pratiques API REST (2024)

**Source** : FastAPI Documentation (fastapi.tiangolo.com)
**Date** : 2024
**Auteur** : Sebastian Ramirez (createur FastAPI)
**Criteres** : Auteur identifie, notoriete internationale, documentation officielle

**Resume** :
Recommandations pour APIs production :
- Utiliser Pydantic pour validation des entrees/sorties
- Documenter avec OpenAPI automatique
- Gerer les erreurs avec HTTPException
- Ajouter healthcheck endpoint
- Injecter les dependances via `Depends()`

**Impact projet** :
- Endpoint `/` healthcheck implemente
- OpenAPI auto-genere sur `/docs`
- Validation Pydantic adoptee sur tous les endpoints (`src/api/schemas.py`)
- Injection de dependances via `Depends()` pour le stockage

---

### 3.3 Parquet vs autres formats (2024)

**Source** : Apache Arrow Blog (arrow.apache.org)
**Date** : 2024
**Auteur** : Apache Arrow PMC
**Criteres** : Projet fondation Apache, documentation officielle, sources citees

**Resume** :
Comparaison formats de stockage :

| Format | Compression | Lecture | Ecriture |
|--------|-------------|---------|----------|
| Parquet | Excellent | Tres bon | Bon |
| CSV | Faible | Moyen | Excellent |
| JSON | Moyen | Moyen | Bon |
| ORC | Bon | Tres bon | Bon |

**Impact projet** :
- Parquet = bon choix pour analytics (ADR-001)
- Compression snappy = equilibre taille/vitesse
- PyArrow (pas pandas) pour memoire efficace (ADR-003)

---

### 3.4 RGPD -- Donnees financieres (2024)

**Source** : CNIL (cnil.fr)
**Date** : 2024
**Auteur** : Commission Nationale de l'Informatique et des Libertes
**Criteres** : Autorite reglementaire francaise, source officielle, reference juridique

**Resume** :
Les donnees de marche crypto (prix, volumes) sont des **donnees publiques** :
- Pas de donnees personnelles (PII)
- Pas de consentement requis
- Pas de registre des traitements obligatoire

Attention : Si le systeme traitait des donnees utilisateurs (portefeuilles personnels), le RGPD s'appliquerait pleinement.

**Impact projet** :
- Donnees Binance = publiques, pas de conformite RGPD complexe requise
- Analyse documentee dans `docs/rapport/07_rgpd.md`

---

### 3.5 UV -- Nouveau gestionnaire Python (2024)

**Source** : Astral (docs.astral.sh)
**Date** : 2024
**Auteur** : Charlie Marsh (createur de ruff et uv)
**Criteres** : Auteur identifie, notoriete (ruff = linter le plus adopte), source officielle

**Resume** :
`uv` est un gestionnaire de dependances Python ultra-rapide :
- 10-100x plus rapide que pip
- Remplace pip, pip-tools, virtualenv
- Compatible pyproject.toml
- Lockfile reproductible

**Impact projet** :
- Adopte pour le projet (`uv sync`, `uv run`)
- Lockfile `uv.lock` pour reproductibilite
- Integre aux Dockerfiles

---

### 3.6 Delta Lake (delta-rs) -- Transactions ACID sur fichiers (2024)

**Source** : delta.io, delta-rs GitHub (delta-io/delta-rs)
**Date** : 2024
**Auteur** : Delta Lake Contributors (Linux Foundation, Databricks)
**Criteres** : Projet fondation Linux, communaute active (5k+ stars), documentation officielle

**Resume** :
Delta Lake apporte les garanties ACID aux fichiers Parquet :
- Transactions atomiques (commit log JSON)
- Time travel (acces aux versions precedentes)
- Schema enforcement et evolution
- delta-rs = implementation Rust native, sans JVM, avec bindings Python

Avantages delta-rs vs Delta Spark :
- Pas de dependance JVM/Spark
- Leger, integrable dans un pipeline Python pur
- Compatible DuckDB via scan de fichiers Parquet sous-jacents

**Impact projet** :
- Adopte comme backend de stockage optionnel (ADR-006)
- `src/storage/delta.py` implemente l'interface `Storage` ABC
- Time travel utile pour audit et reproductibilite des resultats
- Tests : `tests/test_delta_storage.py`

---

### 3.7 dbt-duckdb -- Transforms SQL avec tests et lineage (2024)

**Source** : docs.getdbt.com, GitHub dbt-labs/dbt-duckdb
**Date** : 2024
**Auteur** : dbt Labs (Fisher, createur de dbt)
**Criteres** : Editeur reconnu, outil standard de l'industrie, documentation exhaustive

**Resume** :
dbt (data build tool) permet de definir les transformations en SQL pur :
- Modeles SQL organises en staging / marts
- Tests integres (unique, not_null, relationships, custom)
- Lineage automatique (DAG de dependances)
- dbt-duckdb = adaptateur pour executer les modeles directement sur DuckDB

Architecture recommandee :
- `staging/` : nettoyage et typage des sources brutes
- `marts/` : tables metier (faits, dimensions, agregats)

**Impact projet** :
- Adopte pour la couche de transformation SQL (ADR-007)
- `dbt_project/` avec staging (stg_klines, stg_symbols) et marts (fact_prices, dim_symbol, dim_date, agg_daily_returns, portfolio_summary)
- Tests dbt pour qualite des donnees (volumes positifs, cles uniques)
- Integre dans le DAG Airflow (tache `dbt_run`)
- Tests : `tests/test_dbt_project.py`

---

### 3.8 Kafka / Redpanda -- Streaming temps reel (2024)

**Source** : redpanda.com/blog, kafka.apache.org
**Date** : 2024
**Auteur** : Redpanda Data Inc., Apache Kafka PMC
**Criteres** : Editeurs reconnus, adoption industrielle massive, documentation officielle

**Resume** :
Kafka est la plateforme de reference pour le streaming evenementiel :
- Producteur / Consommateur decouple
- Partitionnement et replication
- Retention configurable

Redpanda = implementation compatible Kafka sans JVM :
- API Kafka identique (protocole wire-compatible)
- Ecrit en C++, auto-tuning
- Console web integree
- Pas de ZooKeeper, deploiement simplifie

**Impact projet** :
- Adopte pour l'ingestion temps reel des donnees Binance
- `src/pipeline/stream_producer.py` : WebSocket Binance -> topic Kafka (klines + order book)
- `src/pipeline/stream_consumer.py` : Kafka -> micro-batch Parquet (zone Bronze)
- Redpanda deploye via Docker Compose (profil `streaming`)
- Console Redpanda sur `http://localhost:8080`
- Tests : `tests/test_streaming.py`

---

## 4. Recommandations issues de la veille

### 4.1 Actions immediates (realisees)

| Action | Priorite | Source veille | Status |
|--------|----------|---------------|--------|
| Utiliser DuckDB derniere version | Haute | 3.1 | Fait |
| Documenter conformite RGPD | Moyenne | 3.4 | Fait |
| Ajouter healthcheck API | Basse | 3.2 | Fait |
| Validation Pydantic sur API | Moyenne | 3.2 | Fait |
| Monitoring Prometheus + Grafana | Moyenne | Veille observabilite | Fait |
| Adopter Delta Lake (delta-rs) | Moyenne | 3.6 | Fait |
| Integrer dbt-duckdb | Moyenne | 3.7 | Fait |
| Deployer streaming Redpanda | Moyenne | 3.8 | Fait |

### 4.2 Actions futures

| Action | Priorite | Echeance |
|--------|----------|----------|
| Tests de charge (API + pipeline) | Basse | v2.0 |

---

## 5. Partage de la veille

### 5.1 Format de diffusion

- Syntheses integrees au rapport projet (ce document)
- Notes techniques dans `docs/architecture/adr/`
- Commits Git avec references aux sources
- Presentation des choix technologiques lors des sprint reviews (cf. `docs/business/meeting_notes/`)

### 5.2 Communication de la synthese aux parties prenantes

La synthese de veille est partagee sous forme accessible a l'ensemble des parties prenantes :
- **Jury** : integree au rapport professionnel, section dediee
- **Equipe projet** : presentee en sprint review avec impact concret sur les decisions
- **Product Owner** : resume non-technique des implications metier

### 5.3 Accessibilite (RGAA)

Conformement au Referentiel General d'Amelioration de l'Accessibilite (RGAA) :

| Critere RGAA | Application |
|--------------|-------------|
| Structuration semantique | Titres hierarchiques (H1, H2, H3) |
| Contraste | Texte noir sur fond blanc, ratio > 4.5:1 |
| Alternative textuelle | Diagrammes en ASCII, pas d'images sans alt-text |
| Navigation | Table des matieres, liens internes |
| Format | Markdown (texte brut structure), exportable en PDF accessible |
| Langue | Document en francais, langue declaree |
| Tableaux | En-tetes de colonnes identifies |
