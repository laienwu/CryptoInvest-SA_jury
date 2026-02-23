# Guide de surveillance et d'alerte

## Présentation

Ce document décrit la stratégie de surveillance de la plateforme d'optimisation de portefeuille. Il couvre la collecte de métriques, les règles d'alerte et les spécifications des tableaux de bord.

---

## 1. Architecture de surveillance

```
┌─────────────────────────────────────────────────────────────────────┐
│                        MONITORING STACK                              │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌───────────────┐    ┌───────────────┐    ┌───────────────┐        │
│  │   Services    │───▶│   Metrics     │───▶│   Alerting    │        │
│  │               │    │   Collector   │    │               │        │
│  │ • API         │    │               │    │ • Email       │        │
│  │ • Airflow     │    │ • Health      │    │ • Slack       │        │
│  │ • Pipeline    │    │ • Logs        │    │               │        │
│  └───────────────┘    └───────────────┘    └───────────────┘        │
│                              │                                       │
│                              ▼                                       │
│                    ┌───────────────────┐                            │
│                    │    Dashboard      │                            │
│                    │                   │                            │
│                    │ • Airflow UI      │                            │
│                    │ • Docker stats    │                            │
│                    │ • Custom scripts  │                            │
│                    └───────────────────┘                            │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Indicateurs clés

### 2.1 Indicateurs d'application

| Métrique | Tapez | Source | Seuil d'alerte |
|--------|------|--------|-----------------|
| Temps de réponse API | Jauge | API rapide | > 500 ms |
| Taux d'erreur API | Compteur | Journaux FastAPI | > 5 % |
| Requêtes API/min | Compteur | API rapide | < 1 (pas d'avertissement de circulation) |
| Durée du pipeline | Jauge | Flux d'air | > 10 minutes |
| Taux de réussite des pipelines | Pourcentage | Flux d'air | < 95 % |
| Fraîcheur des données | Jauge | Fichier mtime | > 24 heures |

### 2.2 Métriques d'infrastructure

| Métrique | Tapez | Source | Seuil d'alerte |
|--------|------|--------|-----------------|
| Processeur du conteneur | Jauge | Statistiques Docker | > 80 % |
| Mémoire de conteneur | Jauge | Statistiques Docker | > 80 % |
| Utilisation du disque | Jauge | df | > 85 % |
| Le conteneur redémarre | Compteur | Événements Dockers | > 3/heure |

### 2.3 Métriques commerciales

| Métrique | Tapez | Source | Seuil d'alerte |
|--------|------|--------|-----------------|
| Ratio de Sharpe du portefeuille | Jauge | poids.json | < 0,5 |
| Nombre d'enregistrements de données | Jauge | CanardDB | < attendu |
| Couverture des symboles | Pourcentage | Lac de données | < 100 % |

---

## 3. Vérifications de l'état

### 3.1 Vérification de l'état de l'API

**Point de terminaison :** `GET /`

**Mise en œuvre :**
```python
@app.get("/")
def health_check():
    return {
        "status": "ok",
        "message": "Portfolio API"
    }
```

**Vérification de l'état de Docker :**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8000/"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 10s
```

### 3.2 Bilan de santé approfondi

**Point de terminaison :** `GET /health/deep` (à implémenter)

**Contrôles :**
- Connectivité de la base de données (DuckDB)
- Fraîcheur des données (fichier horodatages)
- Accessibilité de l'API externe (Binance)

```python
@app.get("/health/deep")
def deep_health_check():
    checks = {
        "database": check_duckdb(),
        "data_freshness": check_data_freshness(),
        "binance_api": check_binance(),
    }
    status = "healthy" if all(c["ok"] for c in checks.values()) else "degraded"
    return {"status": status, "checks": checks}
```

### 3.3 Contrôle de l'état du flux d'air

**Point de terminaison :** `GET http://localhost:8081/health`

**Vérification CLI :**
```bash
docker compose exec airflow-webserver airflow jobs check --job-type SchedulerJob
```

---

## 4. Journalisation

### 4.1 Format de journal

**Format standard (JSON) :**
```json
{
  "timestamp": "2025-01-15T08:32:15.123Z",
  "level": "INFO",
  "service": "api",
  "message": "Request processed",
  "request_id": "abc-123",
  "duration_ms": 45,
  "path": "/portfolio"
}
```

### 4.2 Niveaux de journalisation

| Niveau | Utilisation | Exemples |
|-------|-------|----------|
| ERREUR | Pannes nécessitant une attention | Erreurs d'API, échecs de pipeline |
| AVERTISSEMENT | Problèmes potentiels | Réponses lentes, limitation du débit |
| INFOS | Opérations normales | Demande traitée, tâche terminée |
| DÉBOGAGE | Débogage détaillé | Résultats de la requête, valeurs intermédiaires |

### 4.3 Collecte de journaux

```bash
# View real-time logs
docker compose logs -f --tail=100

# Filter by service
docker compose logs api | grep ERROR

# Save logs to file
docker compose logs > logs/$(date +%Y%m%d).log
```

### 4.4 Conservation des journaux

| Type de journal | Rétention | Emplacement |
|----------|-----------|----------|
| Journaux d'applications | 30 jours | Docker/journal |
| Journaux de tâches Airflow | 90 jours | ./logs/airflow/ |
| Journaux d'accès | 90 jours | ./logs/access/ |

---

## 5. Règles d'alerte

### 5.1 Alertes critiques (P1)

**Déclencher une notification immédiate (e-mail + Slack)**

| Alerte | État | Action |
|-------|-----------|--------|
| API en panne | Le contrôle de santé échoue 3x | Redémarrer le conteneur, faire remonter |
| Échec du pipeline | L'exécution du DAG a échoué | Vérifier les journaux, nouvelle tentative manuelle |
| Corruption des données | Données invalides détectées | Arrêter le pipeline, enquêter |

### 5.2 Alertes d'avertissement (P2)

**Déclencher une notification dans un délai d'une heure**

| Alerte | État | Action |
|-------|-----------|--------|
| Latence élevée | API p95 > 500 ms | Vérifier les ressources |
| Données obsolètes | Aucune mise à jour en 24h | Vérifier le planificateur de flux d'air |
| Faible Sharpe | Sharpe < 0,5 | Notifier les analystes |

### 5.3 Alertes informatives (P3)

**Enregistré, examiné quotidiennement**

| Alerte | État | Action |
|-------|-----------|--------|
| Processeur élevé | > 70% soutenu | Envisagez de mettre à l'échelle |
| Disque 75% | Utilisation du disque > 75 % | Planifier le nettoyage |
| Tarif Limité | Erreur Binance 429 | Fréquence de surveillance |

### 5.4 Configuration des alertes

```yaml
# alerts.yml
alerts:
  - name: api_down
    severity: critical
    condition: health_check_failed
    for: 5m
    channels: [email, slack]
    message: "API health check failing for 5 minutes"

  - name: pipeline_failed
    severity: critical
    condition: dag_run_failed
    channels: [email, slack]
    message: "Portfolio optimization pipeline failed"

  - name: data_stale
    severity: warning
    condition: data_age > 24h
    channels: [slack]
    message: "Data not updated in 24 hours"

  - name: high_latency
    severity: warning
    condition: api_p95_latency > 500ms
    for: 10m
    channels: [slack]
    message: "API latency elevated"
```

---

## 6. Scripts de surveillance

### 6.1 Script de vérification de l'état

```bash
#!/bin/bash
# scripts/health_check.sh

API_URL="http://localhost:8000"
AIRFLOW_URL="http://localhost:8081/health"

# Check API
api_status=$(curl -s -o /dev/null -w "%{http_code}" $API_URL)
if [ "$api_status" != "200" ]; then
    echo "CRITICAL: API returned $api_status"
    exit 2
fi

# Check Airflow
airflow_status=$(curl -s -o /dev/null -w "%{http_code}" $AIRFLOW_URL)
if [ "$airflow_status" != "200" ]; then
    echo "WARNING: Airflow returned $airflow_status"
    exit 1
fi

# Check data freshness
data_age=$(find data/raw/klines -name "*.parquet" -mmin +1440 | wc -l)
if [ "$data_age" -gt 0 ]; then
    echo "WARNING: Data older than 24 hours"
    exit 1
fi

echo "OK: All checks passed"
exit 0
```

### 6.2 Script de collecte de métriques

```python
#!/usr/bin/env python3
# scripts/collect_metrics.py

import json
import subprocess
from datetime import datetime
from pathlib import Path

def collect_metrics():
    metrics = {
        "timestamp": datetime.utcnow().isoformat(),
        "api": check_api(),
        "data": check_data(),
        "resources": check_resources(),
    }
    return metrics

def check_api():
    import requests
    try:
        r = requests.get("http://localhost:8000/", timeout=5)
        return {"status": "up", "response_time_ms": r.elapsed.total_seconds() * 1000}
    except Exception as e:
        return {"status": "down", "error": str(e)}

def check_data():
    parquet_files = list(Path("data/raw/klines").glob("*.parquet"))
    newest = max(f.stat().st_mtime for f in parquet_files) if parquet_files else 0
    age_hours = (datetime.now().timestamp() - newest) / 3600
    return {
        "files": len(parquet_files),
        "age_hours": round(age_hours, 1),
    }

def check_resources():
    result = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}"],
        capture_output=True, text=True
    )
    return [json.loads(line) for line in result.stdout.strip().split("\n") if line]

if __name__ == "__main__":
    metrics = collect_metrics()
    print(json.dumps(metrics, indent=2))
```

---

## 7. Tableaux de bord

### 7.1 Tableau de bord du flux d'air

**URL :** http://localhost:8081

**Vues clés :**
- DAG : liste de tous les DAG avec un statut
- Grille : historique d'exécution des tâches
- Graphique : visualisation de la structure du DAG
- Journaux : niveau de la tâche logs

### 7.2 Tableau de bord de surveillance personnalisé

```
┌─────────────────────────────────────────────────────────────────┐
│                    SYSTEM STATUS DASHBOARD                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  SERVICES                          LAST PIPELINE RUN             │
│  ┌────────────────────────┐       ┌────────────────────────┐    │
│  │ ● API          [UP]    │       │ Status:    ✓ Success   │    │
│  │ ● Airflow      [UP]    │       │ Duration:  3m 42s      │    │
│  │ ● Scheduler    [UP]    │       │ Records:   2,450       │    │
│  │ ● Database     [UP]    │       │ Started:   00:00 UTC   │    │
│  └────────────────────────┘       └────────────────────────┘    │
│                                                                  │
│  RESOURCES                         DATA QUALITY                  │
│  ┌────────────────────────┐       ┌────────────────────────┐    │
│  │ CPU:     ██░░░░░  25%  │       │ Symbols:   5/5  100%   │    │
│  │ Memory:  ████░░░  45%  │       │ Records:   2,450       │    │
│  │ Disk:    ██░░░░░  18%  │       │ Freshness: 2h ago      │    │
│  │ Network: OK            │       │ Nulls:     0           │    │
│  └────────────────────────┘       └────────────────────────┘    │
│                                                                  │
│  ALERTS (Last 24h)                                               │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ⚠ 08:32  API response time > 400ms (resolved)            │   │
│  │ ✓ 00:05  Daily pipeline completed successfully           │   │
│  │ ✓ 00:04  Previous day pipeline completed                 │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Canaux de notification

### 8.1 Configuration de la messagerie

```yaml
# For Airflow email alerts
smtp:
  host: smtp.company.com
  port: 587
  user: alerts@company.com
  password: ${SMTP_PASSWORD}

recipients:
  critical: [devops@company.com, oncall@company.com]
  warning: [data-team@company.com]
  info: [data-team@company.com]
```

### 8.2 Intégration Slack

```bash
# Send Slack alert
curl -X POST -H 'Content-type: application/json' \
  --data '{"text":"Pipeline failed!"}' \
  $SLACK_WEBHOOK_URL
```

---

*Version du document : 1.0*
*Dernière mise à jour : 2025-02-17*
*Propriétaire : Pierre Durand (DevOps)*
