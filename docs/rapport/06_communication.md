# Communication Projet (C7)

## 1. Strategie de communication

### 1.1 Objectifs

- Informer les parties prenantes de l'avancement du projet
- Demonstrer les realisations techniques a chaque jalon
- Justifier les choix techniques et organisationnels tout au long du projet
- Integrer les retours des parties prenantes dans le processus iteratif
- Preparer la validation finale (jury de certification)

### 1.2 Plan de communication

| Etape | Cible | Message | Support | Date |
|-------|-------|---------|---------|------|
| Lancement | Jury / Formateur | Presentation projet, perimetre | Oral + slides | S1 |
| Jalon 1 | Formateur + PO | Pipeline ingest fonctionnel (6 sources) | Demo live | S2 |
| Jalon 2 | Formateur | Metriques calculees (PyArrow) | Demo + rapport | S4 |
| Jalon 3 | Equipe | DWH + dbt operationnel | Sprint review | S6 |
| Jalon 4 | Formateur + PO | API 46 endpoints + dashboard 32 pages | Demo live | S9 |
| Jalon 5 | Equipe | 6 strategies d'optimisation | Sprint review | S12 |
| Jalon 6 | Formateur | Streaming Kafka operationnel | Demo live | S14 |
| Jalon 7 | DevOps | Monitoring Prometheus + Grafana | Dashboard Grafana | S16 |
| Livraison | Jury | Projet complet | Rapport + code | S18 |
| Soutenance | Jury | Validation finale | Oral 1h30 | S18 |

### 1.3 Justification des choix

Tout au long du projet, les choix techniques et organisationnels sont justifies et documentes :

| Type de choix | Justification | Document |
|---------------|---------------|----------|
| Choix techniques | Architecture Decision Records (ADR) | `docs/architecture/adr/` (7 ADR) |
| Choix organisationnels | Methodologie Agile, Scrum | `docs/rapport/05_planification.md` |
| Choix de planning | Chemin critique, estimation collective | `docs/rapport/05_planification.md` |
| Choix de gouvernance | Conformite RGPD, catalogue | `docs/rapport/07_rgpd.md`, `docs/rapport/09_catalogue_donnees.md` |

---

## 2. Supports de communication

### 2.1 Documentation technique

**README.md** (utilisateurs) :
- Quick start avec Docker Compose
- Documentation des profils (streaming, monitoring, airflow, full)
- Liens vers l'API et le dashboard

**CLAUDE.md** (developpeurs / mainteneur) :
- Architecture complete du systeme
- Patterns a respecter (Storage ABC, PipelineConfig, Depends injection)
- Commandes rapides
- Script de demonstration

### 2.2 Documentation API (auto-generee)

Accessible sur `/docs` (Swagger UI) et `/redoc` (ReDoc) :
- 46 endpoints documentes
- Schemas Pydantic (entrees / sorties)
- Try it out interactif
- Specification OpenAPI 3.0 (`docs/architecture/api_specification.yaml`)

### 2.3 Rapport professionnel

Structure du rapport de certification :

| Chapitre | Competence | Document |
|----------|------------|----------|
| 1. Analyse du besoin | C1 | `01_analyse_besoin.md` |
| 2. Cartographie des donnees | C2 | `02_cartographie_donnees.md` |
| 3. Cadre technique | C3 | `03_cadre_technique.md` |
| 4. Veille technologique | C4 | `04_veille.md` |
| 5. Planification et supervision | C5, C6 | `05_planification.md` |
| 6. Communication | C7 | `06_communication.md` (ce document) |
| 7. Conformite RGPD | C21 | `07_rgpd.md` |
| 8. Dimensions a variation lente | C17 | `08_scd_dimensions.md` |
| 9. Catalogue de donnees | C20 | `09_catalogue_donnees.md` |
| 10. Modelisation MERISE | C11 | `10_merise.md` |

### 2.4 Documentation operationnelle

| Document | Contenu | Destinataire |
|----------|---------|--------------|
| Runbook | Procedures operationnelles | DevOps |
| Monitoring | Metriques et alertes | DevOps |
| SLA | Niveaux de service | PO / Client |
| Securite | Checklist de securite | DevOps |
| Incident response | Gestion des incidents | Equipe |

---

## 3. Accessibilite des supports (RGAA)

### 3.1 Criteres respectes

Conformement au Referentiel General d'Amelioration de l'Accessibilite (RGAA) :

| Critere RGAA | Application dans le projet |
|--------------|----------------------------|
| Structuration semantique | Titres hierarchiques (H1, H2, H3) dans tous les documents |
| Contraste | Texte noir sur fond blanc (ratio > 4.5:1) |
| Alternative textuelle | Diagrammes en ASCII art, pas d'images sans attribut alt |
| Navigation | Table des matieres, liens internes |
| Format | Markdown (texte brut structure), exportable en PDF accessible |
| Langue | Documents en francais, langue declaree dans les exports HTML |
| Tableaux | En-tetes de colonnes identifies dans tous les tableaux |
| Slides soutenance | HTML avec structure semantique, contraste respecte (bleu fonce / or) |
| Dashboard Streamlit | Interface web standard, navigation par onglets |
| API documentation | Swagger UI / ReDoc = standards accessibles |

### 3.2 Formats de diffusion

| Support | Format | Accessibilite |
|---------|--------|---------------|
| Rapport | Markdown / PDF | Texte structure, lecteur d'ecran compatible |
| Slides soutenance | HTML (`docs/soutenance.html`) | Semantique, contraste, navigation clavier |
| Code source | Python | Commentaires, docstrings |
| API documentation | HTML (Swagger UI) | Standard OpenAPI |
| Dashboard | Streamlit (web) | Interface standard, labels |
| Grafana dashboards | Web | Interface standard |

---

## 4. Soutenance

### 4.1 Structure de la presentation (1h30 au total)

**Partie 1 : Presentation orale (40 minutes)**

| Section | Duree | Contenu |
|---------|-------|---------|
| Introduction | 3 min | Contexte metier (crypto + finance traditionnelle), besoin, perimetre |
| Architecture Data Lake | 5 min | Bronze/Silver/Gold, 6 sources (C8), Parquet (ADR-001) |
| Entrepot de donnees | 5 min | DuckDB star schema (C13-C14), dbt staging/marts, SQL (C9) |
| Pipeline ETL | 5 min | Airflow DAG (C15-C16), transform PyArrow, validation |
| Exposition | 5 min | FastAPI 46 endpoints (C12), Streamlit 32 pages, Docker |
| Analytics avancees | 5 min | 6 strategies, backtest, Monte Carlo, signaux |
| Streaming & Big Data | 3 min | Kafka/Redpanda, PySpark, Delta Lake |
| Monitoring | 2 min | Prometheus, Grafana, alertes |
| Demonstration live | 5 min | Pipeline complet, API, dashboard |
| Conclusion | 2 min | Bilan, perspectives, competences demontrees |

**Epreuves evaluees :**
- E1 : Collecte, stockage, mise a disposition (C8-C12)
- E2 : Data Warehouse (C13-C17)
- E3 : Data Lake (C18-C21)

**Partie 2 : Questions du jury (50 minutes)**

Session de questions-reponses couvrant l'ensemble des blocs de competences.

### 4.2 Points cles a demontrer

| Competence | Demonstration prevue |
|------------|----------------------|
| C8 (Extraction multi-sources) | `ingest_all_sources()` : API, CSV, JSON, scraping, PostgreSQL, yfinance |
| C9 (Requetes SQL) | Requetes DuckDB live sur fact_prices, dim_symbol |
| C10 (Agregation multi-sources) | `transform.py` : fusion et calcul sur donnees mixtes |
| C11 (Base de donnees MERISE) | MCD/MLD/MPD documentes |
| C12 (API REST) | Swagger UI /docs, 46 endpoints, Pydantic schemas |
| C13 (Faits/Dimensions) | Star schema : fact_prices, dim_symbol, dim_date |
| C14 (Entrepot) | `get_storage("duckdb")`, requetes analytiques |
| C15 (ETL Airflow) | DAG portfolio_dag.py, execution, monitoring |
| C16 (Gestion entrepot) | Scheduling Airflow, logs, retry |
| C17 (Variations dimensions) | SCD Type 1/2 documentees |
| C18 (Architecture Data Lake) | data/ zones Bronze/Silver/Gold + Docker |
| C19 (Integration composants) | Parquet + DuckDB + Delta Lake + Docker Compose |
| C20 (Catalogue) | Catalogue de donnees documente |
| C21 (Gouvernance RGPD) | Analyse RGPD, donnees publiques |

### 4.3 Anticipation des questions du jury

**Architecture et choix techniques :**

| Question probable | Reponse preparee |
|-------------------|------------------|
| Pourquoi DuckDB et pas PostgreSQL ? | DuckDB = OLAP integre, lecture directe Parquet, pas de serveur a gerer. PostgreSQL = OLTP, plus lourd pour l'analytique. ADR-002 documente ce choix. |
| Pourquoi PyArrow au lieu de pandas ? | Memoire O(1) vs O(n) copie, type safety natif, zero-copy vers DuckDB/Parquet. Pandas utilise en interne par yfinance mais converti immediatement en Arrow. ADR-003. |
| Comment scale le systeme ? | Storage pluggable (ABC + factory), ajout de backends sans modifier le pipeline. Delta Lake pour ACID. Kafka pour decouplage. PySpark pour gros volumes. |
| Pourquoi Redpanda et pas Kafka natif ? | API wire-compatible, pas de JVM, deploiement simplifie (1 binaire), auto-tuning. Memes garanties. |

**Points de friction techniques (retours d'experience) :**

| Point | Explication |
|-------|-------------|
| Gestion des credentials Binance | Variables d'environnement, jamais dans le code. `.env` dans `.gitignore`. |
| Annualisation de la volatilite | Facteur sqrt(365) pour crypto (marche 24/7), sqrt(252) pour actions. Configurable dans PipelineConfig. |
| Calcul du ratio de Sharpe | Rf (taux sans risque) = 0 par defaut pour crypto. Configurable. Annualise coheremment avec la volatilite. |
| Delta Lake sans Spark | delta-rs = implementation Rust native, bindings Python. Pas de JVM necessaire. Compatible DuckDB via scan Parquet. |
| PySpark en local | SparkSession locale pour le developpement. En production, cluster Spark. Les transforms sont testables unitairement. |
| Chemins dbt | `profiles.yml` local, chemin DuckDB relatif. Integre dans le DAG Airflow via BashOperator. |
| Isolation du streaming | Profil Docker Compose `streaming` separe. Producer et consumer independants du pipeline batch. |
| Strategie de mock dans les tests | Storage injecte via factory, API via Depends override. Pas de dependance externe dans les tests (748 tests, 0 appel reseau). |
| Couverture de code | 37 fichiers de tests, couvrant chaque module du pipeline. CI GitHub Actions execute tous les tests a chaque push. |
| Taux sans risque (Rf) | Defaut 0 pour crypto (pas de benchmark sans risque etabli). Pour les actifs traditionnels, utilisation du taux du tresor US. |

**Limites et perspectives :**

| Question probable | Reponse preparee |
|-------------------|------------------|
| Limites du projet ? | Pas de ML/prediction, pas de deploiement cloud, donnees historiques uniquement (pas de live trading). Streaming = preuve de concept. |
| Ameliorations futures ? | Tests de charge, deploiement Kubernetes, ML pour prediction de regime, portfolio multi-asset elargi. |
| Pourquoi pas le cloud ? | Projet academique, budget 0 EUR. L'architecture est cloud-ready (Docker, S3 via MinIO, Kafka via Redpanda). |

---

## 5. Retours des parties prenantes

### 5.1 Processus de collecte des retours

| Source | Methode | Frequence | Documentation |
|--------|---------|-----------|---------------|
| Product Owner (Marie Dupont) | Sprint review + validation fonctionnelle | Bi-mensuelle | `docs/business/meeting_notes/` |
| Formateur | Points hebdomadaires | Hebdomadaire | Notes de reunion |
| Business Analyst (Jean-Martin) | Revue de documentation | Par phase | Commentaires sur PR |
| Data Analyst (Sophie Bernard) | Validation des calculs financiers | Par module | Tests de non-regression |
| Jury | Soutenance finale | Unique | Grille d'evaluation |

### 5.2 Integration des retours

Le processus d'integration des retours suit un cycle structure :

1. **Collecte** : retours documentes lors des sprint reviews et points hebdomadaires
2. **Priorisation** : classement par impact (bloquant / important / mineur) avec le PO
3. **Planification** : integration dans le sprint suivant (backlog)
4. **Implementation** : developpement + tests
5. **Validation** : demonstration au demandeur lors du sprint review suivant
6. **Documentation** : mise a jour du rapport et des artefacts impactes

### 5.3 Exemples de retours integres

| Retour | Source | Action | Sprint |
|--------|--------|--------|--------|
| Ajouter des actifs traditionnels | PO | Integration yfinance (actions, ETF, matieres premieres) | S4 |
| Comparer les strategies | PO | Page Strategy Showdown (6 optimiseurs cote a cote) | S12 |
| Documenter la gouvernance | Formateur | Rapport RGPD + catalogue de donnees | S6 |
| Valider les calculs de Sharpe | Data Analyst | Tests unitaires specifiques, annualisation verifiee | S5 |
| Monitoring en production | DevOps | Prometheus + Grafana + alertes | S15 |

---

## 6. Livrables finaux

### 6.1 Checklist de livraison

| Livrable | Format | Status |
|----------|--------|--------|
| Code source | Git repo (GitHub) | Fait |
| README.md | Markdown | Fait |
| CLAUDE.md (instructions mainteneur) | Markdown | Fait |
| Documentation technique (ADR, C4, OpenAPI) | Markdown / YAML | Fait |
| Documentation operationnelle (runbook, monitoring, SLA) | Markdown | Fait |
| Documentation metier (user stories, RACI, KPI) | Markdown | Fait |
| Rapport certification (10 documents) | Markdown | Fait |
| Slides soutenance | HTML | Fait |
| Demo fonctionnelle | Docker Compose | Fait |
| Tests automatises | pytest (748 tests) | Fait |
| CI/CD | GitHub Actions | Fait |

### 6.2 Arborescence finale du projet

```
binance/
 -- src/
 |   -- config.py                        # Configuration centralisee (PipelineConfig)
 |   -- pipeline/                        # ETL + analytics (30+ modules)
 |   |   -- ingest.py                   # Binance API
 |   |   -- ingest_sources.py           # Multi-sources (DataSource ABC)
 |   |   -- ingest_scraping.py          # CoinGecko scraping
 |   |   -- ingest_postgres.py          # PostgreSQL benchmarks
 |   |   -- ingest_yfinance.py          # Yahoo Finance
 |   |   -- transform.py               # Rendements, volatilite, correlation
 |   |   -- optimize.py                # Markowitz + frontiere efficiente
 |   |   -- backtest.py                # Walk-forward backtesting
 |   |   -- monte_carlo.py             # Simulation Monte Carlo
 |   |   -- signals.py                 # Signaux de trading
 |   |   -- regime.py                  # Detection de regime
 |   |   -- pairs.py                   # Pair trading / cointegration
 |   |   -- hrp.py                     # Hierarchical Risk Parity
 |   |   -- black_litterman.py         # Black-Litterman
 |   |   -- risk_parity.py             # Risk Parity
 |   |   -- min_variance.py            # Minimum Variance
 |   |   -- max_diversification.py     # Maximum Diversification
 |   |   -- factor_analysis.py         # Analyse factorielle
 |   |   -- tail_risk.py               # Risque extreme
 |   |   -- strategy_compare.py        # Comparaison des 6 strategies
 |   |   -- spark_transforms.py        # PySpark transforms
 |   |   -- data_metrics.py            # Metriques de donnees
 |   |   -- stream_producer.py         # WebSocket -> Kafka
 |   |   -- stream_consumer.py         # Kafka -> Parquet
 |   |   -- validation.py              # Validation qualite
 |   |   -- [+ 15 autres modules]
 |   -- storage/                         # Backends de stockage
 |   |   -- base.py                     # Interface abstraite (ABC)
 |   |   -- parquet.py                  # Parquet (defaut)
 |   |   -- duckdb.py                   # DuckDB (DWH)
 |   |   -- delta.py                    # Delta Lake
 |   |   -- minio.py                    # MinIO (S3)
 |   -- api/                             # API REST
 |   |   -- main.py                     # FastAPI (46 endpoints)
 |   |   -- schemas.py                  # Modeles Pydantic
 |   |   -- cache.py                    # Cache Redis
 |   |   -- metrics.py                  # Metriques Prometheus
 |   -- dashboard/                       # Visualisation
 |       -- app.py                      # Streamlit (32 pages)
 -- dags/
 |   -- portfolio_dag.py                 # DAG Airflow
 -- dbt_project/                         # dbt-duckdb
 |   -- dbt_project.yml
 |   -- profiles.yml
 |   -- models/
 |   |   -- staging/                    # stg_klines, stg_symbols
 |   |   -- marts/                      # fact_prices, dim_symbol, dim_date, agg_daily_returns
 |   -- macros/
 |   -- tests/
 -- data/
 |   -- raw/                             # Zone Bronze
 |   -- processed/                       # Zone Silver
 |   -- output/                          # Zone Gold
 |   -- reference/                       # Donnees de reference
 -- tests/                               # 37 fichiers, 748 tests
 -- docs/
 |   -- soutenance.html                  # Slides HTML (presentation)
 |   -- rapport/                         # 10 documents certification
 |   |   -- 01_analyse_besoin.md        # C1
 |   |   -- 02_cartographie_donnees.md  # C2
 |   |   -- 03_cadre_technique.md       # C3
 |   |   -- 04_veille.md               # C4
 |   |   -- 05_planification.md        # C5, C6
 |   |   -- 06_communication.md        # C7
 |   |   -- 07_rgpd.md                 # C21
 |   |   -- 08_scd_dimensions.md       # C17
 |   |   -- 09_catalogue_donnees.md    # C20
 |   |   -- 10_merise.md               # C11
 |   -- architecture/                    # Documentation technique
 |   |   -- c4_architecture.md          # Diagrammes C4
 |   |   -- api_specification.yaml      # OpenAPI 3.0
 |   |   -- adr/                        # 7 ADR
 |   -- operations/                      # Documentation DevOps
 |   |   -- runbook.md
 |   |   -- monitoring.md
 |   |   -- sla.md
 |   |   -- security_checklist.md
 |   |   -- incident_response.md
 |   -- business/                        # Documentation metier
 |       -- user_stories.md
 |       -- raci_matrix.md
 |       -- kpi_dashboard.md
 |       -- meeting_notes/              # 4 comptes-rendus
 -- monitoring/                          # Observabilite
 |   -- prometheus.yml
 |   -- alerts.yml
 |   -- grafana/
 |       -- provisioning/
 |       -- dashboards/
 -- .github/
 |   -- workflows/
 |       -- ci.yml                      # CI GitHub Actions
 -- Dockerfile                           # API
 -- Dockerfile.airflow                   # Airflow
 -- Dockerfile.streamlit                 # Dashboard
 -- Dockerfile.streaming                 # Kafka producer/consumer
 -- Dockerfile.spark                     # PySpark
 -- docker-compose.yml                   # Tous les services (profiles)
 -- pyproject.toml                       # Dependances (uv)
 -- uv.lock                             # Lockfile
 -- CLAUDE.md                            # Instructions mainteneur
 -- README.md                            # Documentation utilisateur
```
