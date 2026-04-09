# Conformite RGPD et Gouvernance des Donnees (C21)

## 1. Analyse des donnees traitees

### 1.1 Nature des donnees

| Type de donnee | Exemple | Personnel ? |
|----------------|---------|-------------|
| Prix OHLCV | BTC: 95000 USD | Non |
| Volume | 1000 BTC echanges | Non |
| Timestamp | 2025-01-15 | Non |
| Symbol | BTCUSDT | Non |
| Metriques calculees | Rendement: +2% | Non |
| Actifs traditionnels (yfinance) | SPY: 520.30 USD | Non |

### 1.2 Conclusion

**Aucune donnee personnelle (PII) n'est traitee dans ce projet.**

Les donnees proviennent de sources publiques (API Binance, Yahoo Finance via yfinance, CoinGecko) et representent des informations de marche agregees, anonymes par nature.

---

## 2. Applicabilite du RGPD

### 2.1 Criteres d'applicabilite

| Critere RGPD | Applicable ? | Justification |
|--------------|--------------|---------------|
| Donnees personnelles | Non | Donnees de marche uniquement |
| Personnes physiques identifiables | Non | Donnees agregees |
| Traitement automatise | Oui | Pipeline ETL |
| Etablissement dans l'UE | Oui | Projet certification FR |

### 2.2 Conclusion

Le RGPD **ne s'applique pas** a ce projet car aucune donnee personnelle n'est collectee, stockee ou traitee.

Cependant, par bonne pratique et anticipation d'evolutions futures, nous documentons les mesures qui seraient necessaires et appliquons des principes de gouvernance des donnees.

---

## 3. Mesures preventives

### 3.1 Si le projet evoluait vers des donnees personnelles

**Scenarios futurs possibles :**
- Portefeuilles utilisateurs nominatifs
- Historique de transactions personnelles
- Preferences d'investissement

**Mesures a implementer :**

| Mesure | Description |
|--------|-------------|
| Registre des traitements | Documenter tous les traitements PII |
| Base legale | Consentement ou interet legitime |
| Minimisation | Ne collecter que le necessaire |
| Duree de conservation | Definir et appliquer des limites |
| Droit d'acces | API pour export donnees utilisateur |
| Droit a l'effacement | Procedure de suppression |
| Securite | Chiffrement, acces restreints |

### 3.2 Architecture privacy-by-design actuelle

Meme sans PII, le projet applique des principes de bonne gouvernance :

| Principe | Application |
|----------|-------------|
| Minimisation | Seules les donnees necessaires sont stockees |
| Transparence | Sources documentees (Binance public API, yfinance, CoinGecko) |
| Securite | Docker isolation, pas d'exposition externe |
| Tracabilite | Logs, Git history, Airflow audit trail |
| Qualite | Validation automatisee a chaque etage du pipeline (`src/pipeline/validation.py`) |

---

## 4. Registre des traitements (preventif)

### 4.1 Traitement : Collecte donnees marche crypto

| Champ | Valeur |
|-------|--------|
| **Nom du traitement** | Ingestion donnees OHLCV crypto |
| **Responsable** | Laien Wu |
| **Finalite** | Analyse de marche, optimisation portefeuille |
| **Base legale** | N/A (pas de PII) |
| **Categories de donnees** | Prix, volumes, timestamps |
| **Sources** | API Binance, CoinGecko (scraping), CSV, JSON |
| **Destinataires** | Usage interne uniquement |
| **Transferts hors UE** | Oui (API Binance - serveurs globaux) |
| **Duree de conservation** | 1 an |
| **Mesures de securite** | Stockage local, Docker |

### 4.2 Traitement : Collecte donnees marche traditionnel

| Champ | Valeur |
|-------|--------|
| **Nom du traitement** | Ingestion donnees yfinance (actions, ETF, matieres premieres) |
| **Responsable** | Laien Wu |
| **Finalite** | Diversification portefeuille, benchmarks, analyse alpha/beta |
| **Base legale** | N/A (pas de PII) |
| **Categories de donnees** | Prix OHLCV, volumes, symboles (SPY, QQQ, GLD, etc.) |
| **Sources** | Yahoo Finance via yfinance |
| **Destinataires** | Usage interne uniquement |
| **Transferts hors UE** | Oui (Yahoo Finance - serveurs US) |
| **Duree de conservation** | 1 an |
| **Mesures de securite** | Stockage local, Docker |

### 4.3 Traitement : Calcul metriques

| Champ | Valeur |
|-------|--------|
| **Nom du traitement** | Transformation donnees |
| **Responsable** | Laien Wu |
| **Finalite** | Calcul rendements, volatilite, correlations |
| **Donnees entree** | OHLCV (pas de PII) |
| **Donnees sortie** | Metriques agregees |
| **Duree de conservation** | 1 an |

### 4.4 Traitement : Exposition API

| Champ | Valeur |
|-------|--------|
| **Nom du traitement** | API REST consultation |
| **Responsable** | Laien Wu |
| **Finalite** | Mise a disposition des resultats |
| **Authentification** | Aucune (MVP) |
| **Logs** | Acces non nominatifs |

**Note importante :** L'API FastAPI ne dispose actuellement d'aucune authentification (version MVP). En production, il est recommande d'ajouter :
- Authentification JWT ou OAuth2 pour identifier les appelants
- Rate limiting par cle API
- HTTPS obligatoire (TLS)
- Journalisation des acces avec identite de l'appelant

---

## 5. Gouvernance des acces par groupes

Les droits d'acces sont appliques a des **groupes** et non a des individus, conformement aux bonnes pratiques de gouvernance des donnees.

### 5.1 Definition des groupes

| Groupe | Description | Membres types |
|--------|-------------|---------------|
| **Admin** | Administration du systeme, maintenance, deploiement | Ingenieur de donnees (Laien Wu) |
| **Analyst** | Consultation des donnees transformees et resultats d'optimisation | Analyste de donnees, Product Owner |
| **Application** | Acces programmatique (API, DAG, services Docker) | Services Airflow, FastAPI, Streamlit |

### 5.2 Matrice des droits par zone de donnees

| Zone | Admin | Analyst | Application |
|------|-------|---------|-------------|
| `data/raw/` (Bronze) | Lecture / Ecriture / Suppression | Aucun acces | Ecriture (ingestion) |
| `data/processed/` (Silver) | Lecture / Ecriture / Suppression | Lecture seule | Ecriture (transformation) |
| `data/output/` (Gold) | Lecture / Ecriture / Suppression | Lecture seule | Ecriture (optimisation) |
| `data/reference/` | Lecture / Ecriture | Lecture seule | Lecture seule |
| DuckDB (warehouse) | Toutes operations | SELECT uniquement | SELECT / INSERT (ETL) |
| API FastAPI | Configuration, monitoring | Consultation endpoints | N/A |
| Airflow | Administration DAG | Visualisation DAG | Execution taches |

### 5.3 Principes appliques

- **Moindre privilege** : chaque groupe n'a acces qu'aux donnees necessaires a ses fonctions
- **Separation des responsabilites** : les analystes ne modifient pas les donnees brutes
- **Acces par groupe, pas par individu** : les droits sont attribues au role, pas a la personne
- **Tracabilite** : les acces sont journalises via les logs applicatifs et Airflow

### 5.4 Implementation technique actuelle

Dans le contexte MVP (equipe de 1 personne), la separation est logique et documentee. En production, l'implementation technique s'appuierait sur :
- Permissions filesystem (POSIX groups) pour les zones du data lake
- Roles DuckDB pour l'entrepot
- Middleware d'authentification FastAPI (JWT) pour l'API
- Profils Airflow RBAC pour l'orchestrateur

---

## 6. Gouvernance conjointe Data Lake et Entrepot

### 6.1 Lien entre Data Lake et Data Warehouse

Le data lake et l'entrepot de donnees sont deux composants complementaires du systeme de stockage. Leur gouvernance est coordonnee pour assurer la coherence des donnees a travers tout le pipeline.

```
Data Lake (Parquet)                    Data Warehouse (DuckDB)
┌─────────────────────┐                ┌──────────────────────┐
│ Bronze (raw/)       │ ── ingestion ──│                      │
│   Donnees brutes    │                │   fact_prices        │
│                     │                │   (vue sur Parquet)  │
├─────────────────────┤                │                      │
│ Silver (processed/) │ ── transform ──│   dim_symbol         │
│   Metriques         │                │   dim_date           │
│                     │                │                      │
├─────────────────────┤                │   dbt models:        │
│ Gold (output/)      │ ── optimize ──▶│   - stg_klines       │
│   Poids, resultats  │                │   - agg_daily_returns│
└─────────────────────┘                └──────────────────────┘
```

### 6.2 Regles de gouvernance transversale

| Regle | Data Lake | Data Warehouse | Responsable |
|-------|-----------|----------------|-------------|
| Schema enforcement | Validation PyArrow a l'ecriture | Contraintes SQL + dbt tests | Admin |
| Qualite des donnees | `validation.py` (bronze/silver/gold) | dbt schema tests (unique, not_null) | Admin |
| Retention | Purge automatisee (voir section 7) | Recalcul des vues | Admin |
| Catalogue | `09_catalogue_donnees.md` | dbt documentation (lineage) | Admin |
| Acces | Permissions filesystem par groupe | Roles SQL par groupe | Admin |
| Tracabilite | Horodatage fichiers, Delta Lake time travel | Logs DuckDB, Airflow audit | Admin |

### 6.3 Validation automatisee de la qualite (`src/pipeline/validation.py`)

Le module `validation.py` implemente des controles de qualite automatises a chaque etage du pipeline :

| Etage | Controles | Exemple |
|-------|-----------|---------|
| **Bronze** | Schema OHLCV complet, pas de nulls, prix > 0, nombre minimum d'enregistrements | `validate_stage("bronze", raw_data)` |
| **Silver** | Rendements dans une plage raisonnable, volatilite > 0, matrices symetriques | `validate_stage("silver", processed_data)` |
| **Gold** | Poids dans [0, 1], somme des poids = 1 | `validate_stage("gold", output_data)` |

Chaque validation produit un `ValidationReport` avec un resume pass/fail. Ces controles sont executes automatiquement dans le pipeline ETL et peuvent etre integres comme tache Airflow.

---

## 7. Procedures de tri et de purge

### 7.1 Politique de retention

| Zone | Retention maximale | Critere de tri | Frequence de purge | Mode |
|------|-------------------|----------------|--------------------|----- |
| `data/raw/` (Bronze) | 1 an | Age du fichier (date de modification) | Mensuelle | Automatise |
| `data/processed/` (Silver) | 1 an | Age du fichier (date de modification) | Mensuelle | Automatise |
| `data/output/` (Gold) | 30 jours | Age du fichier (date de modification) | Hebdomadaire | Automatise |
| `data/reference/` | Illimitee | Donnees de reference statiques | Manuelle (revue annuelle) | Manuel |
| DuckDB (warehouse) | Alignee sur le data lake | Recalcul des vues apres purge lake | Apres chaque purge lake | Automatise |

### 7.2 Script de purge automatisee

```python
# scripts/purge_old_files.py
from pathlib import Path
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

PURGE_RULES = {
    "data/raw/": 365,        # 1 an
    "data/processed/": 365,  # 1 an
    "data/output/": 30,      # 30 jours
}

def purge_old_files(directory: Path, max_age_days: int) -> int:
    """Supprime les fichiers dont la date de modification depasse max_age_days."""
    cutoff = datetime.now() - timedelta(days=max_age_days)
    deleted = 0
    for file in directory.glob("**/*"):
        if file.is_file() and file.stat().st_mtime < cutoff.timestamp():
            logger.info("Purge: %s (age > %d jours)", file, max_age_days)
            file.unlink()
            deleted += 1
    return deleted

def run_purge():
    """Execute la purge sur toutes les zones configurees."""
    for zone, max_age in PURGE_RULES.items():
        path = Path(zone)
        if path.exists():
            count = purge_old_files(path, max_age)
            logger.info("Zone %s: %d fichiers supprimes", zone, count)
```

### 7.3 Integration dans l'orchestration

La purge peut etre declenchee via une tache Airflow dediee dans le DAG (`dags/portfolio_dag.py`), planifiee mensuellement. Elle peut egalement etre executee manuellement par l'administrateur.

---

## 8. Securite des donnees

### 8.1 Mesures techniques

| Mesure | Implementation |
|--------|----------------|
| Isolation | Docker containers (chaque service isole) |
| Acces reseau | Port 8000 local uniquement |
| Chiffrement transit | HTTPS vers Binance et Yahoo Finance |
| Chiffrement repos | Non (donnees publiques) |
| Backup | Volume Docker persistant |
| Authentification API | Aucune (MVP) — a ajouter en production |

### 8.2 Mesures organisationnelles

| Mesure | Implementation |
|--------|----------------|
| Acces limites | Gouvernance par groupes (section 5) |
| Documentation | Ce rapport |
| Revue de code | Pull requests, CI/CD (GitHub Actions) |
| Gestion des secrets | Variables d'environnement, pas de credentials en dur |

---

## 9. Procedures de conformite

### 9.1 Procedure de suppression

```
SI demande de suppression recue:
    1. Identifier les donnees concernees
    2. Supprimer de data/raw/
    3. Supprimer de data/processed/
    4. Supprimer de data/output/
    5. Recalculer les vues DuckDB
    6. Confirmer suppression
FIN
```

**Note** : Non applicable actuellement (pas de PII).

### 9.2 Procedure d'export (droit d'acces)

```
SI demande d'export recue:
    1. Identifier les donnees utilisateur
    2. Generer export JSON via l'API FastAPI
    3. Transmettre de maniere securisee
FIN
```

**Note** : Non applicable actuellement (pas de PII).

---

## 10. Conclusion

### 10.1 Synthese conformite

| Aspect | Status |
|--------|--------|
| Donnees personnelles | Aucune |
| RGPD applicable | Non |
| Bonnes pratiques gouvernance | Appliquees |
| Gouvernance par groupes | Documentee (Admin, Analyst, Application) |
| Gouvernance Data Lake + Entrepot | Coordonnee |
| Validation qualite automatisee | `src/pipeline/validation.py` |
| Procedures de tri | Automatisees, frequence mensuelle |
| Documentation | Complete |
| Evolutivite | Mesures preventives documentees |

### 10.2 Recommandations futures

Si le projet evolue vers le traitement de donnees personnelles :

1. Mettre a jour ce registre
2. Implementer les procedures documentees
3. Ajouter authentification a l'API (JWT/OAuth2)
4. Chiffrer les donnees au repos
5. Nommer un DPO si necessaire
6. Implementer les permissions filesystem par groupe (POSIX)
7. Activer les roles DuckDB pour l'entrepot
