# Runbook d'opérations

## Présentation

Ce runbook fournit des procédures opérationnelles pour la plateforme d'optimisation de portefeuille. Public cible : ingénieurs DevOps, assistance d'astreinte, administrateurs système.

---

## 1. Architecture système

```
┌─────────────────────────────────────────────────────────────────┐
│                        DOCKER HOST                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │     API      │  │   Airflow    │  │   Airflow    │           │
│  │   :8000      │  │  Webserver   │  │  Scheduler   │           │
│  │              │  │    :8081     │  │              │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐                             │
│  │  PostgreSQL  │  │  PostgreSQL  │                             │
│  │  (Airflow)   │  │ (Benchmarks) │                             │
│  │    :5432     │  │    :5433     │                             │
│  └──────────────┘  └──────────────┘                             │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                    VOLUMES                                  │ │
│  │  ./data  │  ./dags  │  ./logs  │  postgres_data            │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Gestion des services

### 2.1 Démarrer les services

```bash
# Start API only (minimal)
docker compose up -d api

# Start full stack (API + Airflow)
docker compose --profile airflow up -d

# Start with benchmarks database
docker compose --profile full up -d

# Check all services
docker compose ps
```

### 2.2 Arrêter les services

```bash
# Stop all services
docker compose down

# Stop and remove volumes (DATA LOSS!)
docker compose down -v

# Stop specific service
docker compose stop api
```

### 2.3 Redémarrer les services

```bash
# Restart API (zero-downtime)
docker compose restart api

# Force recreate (config changes)
docker compose up -d --force-recreate api

# Rolling restart Airflow
docker compose restart airflow-scheduler
docker compose restart airflow-webserver
```

### 2.4 Vérifications de l'état du service

```bash
# API health
curl http://localhost:8000/

# Airflow health
curl http://localhost:8081/health

# Check container health
docker inspect --format='{{.State.Health.Status}}' portfolio-api
```

---

## 3. Opérations courantes

### 3.1 Exécution manuelle du pipeline

```bash
# Run full pipeline manually
docker compose --profile pipeline up pipeline

# Or run from inside container
docker compose exec api python -c "
from src.pipeline import ingest_all_sources, transform_data, optimize_portfolio
from src.pipeline.optimize import compute_and_save_frontier
from src.pipeline.backtest import run_backtest

ingest_all_sources()
transform_data()
optimize_portfolio()
compute_and_save_frontier()
run_backtest()
"
```

### 3.2 Afficher les journaux

```bash
# All logs
docker compose logs -f

# Specific service
docker compose logs -f api

# Last 100 lines
docker compose logs --tail=100 api

# Airflow task logs
docker compose exec airflow-webserver cat /opt/airflow/logs/dag_id=portfolio_optimization/run_id=*/task_id=ingest_data/*.log
```

### 3.3 Accéder au shell du conteneur

```bash
# API container
docker compose exec api /bin/bash

# Airflow container
docker compose exec airflow-webserver /bin/bash

# Run Python interactively
docker compose exec api python
```

### 3.4 Opérations de base de données

```bash
# DuckDB CLI (read-only)
docker compose exec api python -c "
import duckdb
conn = duckdb.connect('data/warehouse.duckdb')
print(conn.execute('SELECT COUNT(*) FROM fact_prices').fetchone())
"

# PostgreSQL (benchmarks)
docker compose exec postgres-benchmarks psql -U portfolio -d portfolio_benchmarks

# Backup DuckDB
cp data/warehouse.duckdb data/warehouse.duckdb.backup
```

---

## 4. Dépannage

### L'API 4.1 ne répond pas

**Symptômes :** `curl localhost:8000` expire ou revient erreur

**Diagnostic :**
```bash
# Check if container is running
docker compose ps api

# Check container logs
docker compose logs --tail=50 api

# Check port binding
netstat -tlnp | grep 8000
```

**Résolution :**
```bash
# Restart container
docker compose restart api

# If persists, recreate
docker compose up -d --force-recreate api

# Check for port conflict
lsof -i :8000
```

### 4.2 Le DAG Airflow ne fonctionne pas

**Symptômes :** Le DAG affiche « Aucune exécution » ou est bloqué dans « en file d'attente »

**Diagnostic :**
```bash
# Check scheduler is running
docker compose ps airflow-scheduler

# Check scheduler logs
docker compose logs --tail=100 airflow-scheduler

# Check DAG is not paused
# Visit http://localhost:8081 → Toggle DAG on
```

**Résolution :**
```bash
# Restart scheduler
docker compose restart airflow-scheduler

# Clear failed task
docker compose exec airflow-webserver airflow tasks clear portfolio_optimization -s 2025-01-01

# Trigger manual run
docker compose exec airflow-webserver airflow dags trigger portfolio_optimization
```

### 4.3 Problèmes de qualité des données

**Symptômes :** L'API renvoie des valeurs inattendues et des réponses vides

**Diagnostic :**
```bash
# Check data files exist
ls -la data/raw/klines/
ls -la data/processed/
ls -la data/output/  # Should contain weights.json, frontier.json, backtest.json

# Check file contents
docker compose exec api python -c "
import pyarrow.parquet as pq
table = pq.read_table('data/raw/klines/BTCUSDT.parquet')
print(table.num_rows, 'rows')
print(table.schema)
"

# Check DuckDB tables
docker compose exec api python -c "
import duckdb
conn = duckdb.connect('data/warehouse.duckdb')
print(conn.execute('SELECT symbol, COUNT(*) FROM fact_prices GROUP BY symbol').fetchall())
"
```

**Résolution :**
```bash
# Re-run full pipeline (including frontier and backtest)
docker compose --profile pipeline up pipeline

# Or re-run frontier/backtest individually
docker compose exec api python -c "
from src.pipeline.optimize import compute_and_save_frontier
from src.pipeline.backtest import run_backtest
compute_and_save_frontier()
run_backtest()
"

# Clear and rebuild warehouse
rm data/warehouse.duckdb
docker compose exec api python -c "from src.storage.duckdb import DuckDBStorage; DuckDBStorage().initialize()"
```

### 4.4 Espace disque insuffisant

**Symptômes :** Crash des conteneurs, erreurs « aucun espace restant sur l'appareil »

**Diagnostic :**
```bash
# Check disk usage
df -h

# Check Docker usage
docker system df

# Find large files
du -sh data/*
```

**Résolution :**
```bash
# Remove old Docker artifacts
docker system prune -a

# Remove old data (keep last 30 days)
find data/raw/klines/ -mtime +30 -delete

# Compact DuckDB
docker compose exec api python -c "
import duckdb
conn = duckdb.connect('data/warehouse.duckdb')
conn.execute('VACUUM')
"
```

### Erreurs de l'API Binance 4.5

**Symptômes :** L'ingestion échoue avec "429 demandes de trop" ou "IP interdite"

**Diagnostic :**
```bash
# Check ingestion logs
docker compose logs api | grep -i "binance\|429\|banned"

# Test API connectivity
curl -s "https://api.binance.com/api/v3/ping"
```

**Résolution :**
```bash
# Wait for rate limit reset (usually 1 minute)
sleep 60

# If IP banned, wait 24 hours or use VPN

# Reduce request rate in config
# Edit config.toml: rate_limit_delay = 1.0
```

---

## 5. Sauvegarde et récupération

### 5.1 Procédures de sauvegarde

```bash
# Daily backup script
#!/bin/bash
BACKUP_DIR=/backups/$(date +%Y%m%d)
mkdir -p $BACKUP_DIR

# Backup data
tar -czf $BACKUP_DIR/data.tar.gz data/

# Backup configuration
cp config.toml $BACKUP_DIR/
cp docker-compose.yml $BACKUP_DIR/

# Backup Airflow metadata
docker compose exec airflow-webserver airflow db export $BACKUP_DIR/airflow.json

echo "Backup completed: $BACKUP_DIR"
```

### 5.2 Procédures de récupération

```bash
# Stop services
docker compose down

# Restore data
tar -xzf /backups/YYYYMMDD/data.tar.gz

# Restart services
docker compose up -d
```

### 5.3 Reprise après sinistre

**Scénario :** Perte complète de données

**Objectif de temps de récupération (RTO) :** < 1 heure
**Objectif de point de récupération (RPO) :** < 24 heures

```bash
# 1. Deploy fresh infrastructure
docker compose up -d

# 2. Re-fetch all data from APIs (90-day window)
docker compose exec api python -c "
from src.pipeline.ingest import fetch_klines
for symbol in ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'ADAUSDT']:
    fetch_klines(symbol, days=90)
"

# 3. Run full pipeline
docker compose --profile pipeline up pipeline

# 4. Verify data
curl http://localhost:8000/portfolio
curl http://localhost:8000/portfolio/frontier
curl http://localhost:8000/portfolio/backtest
```

---

## 6. Optimisation des performances

### 6.1 Performances de l'API

```bash
# Increase Uvicorn workers
# In Dockerfile or docker-compose.yml:
# CMD ["uvicorn", "src.api.main:app", "--workers", "4"]

# Enable response caching (nginx)
# Add nginx reverse proxy with caching
```

### 6.2 Performances du pipeline

```bash
# Run ingestion in parallel
# Edit ingest.py: use ThreadPoolExecutor for multiple symbols

# Increase DuckDB memory
# In code: duckdb.connect(':memory:', config={'memory_limit': '2GB'})
```

---

## 7. Contact et escalade

| Niveau | Contacter | Temps de réponse |
|-------|---------|---------------|
| L1 - Astreinte | devops@company.com | < 15 min |
| L2 - Ingénierie des Données | data-team@company.com | < 1 heure |
| L3 -Architecture | Laien Wu | < 4 heures |

**Critères d'escalade :**
- L1 → L2 : problème non résolu en 30 minutes
- L2 → L3 : corruption de données, incident de sécurité, changement d'architecture nécessaire

---

*Version du document : 1.0*
*Dernière mise à jour : 2025-02-17*
*Propriétaire : Pierre Durand (DevOps)*

