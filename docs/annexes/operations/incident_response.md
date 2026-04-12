# Plan de réponse aux incidents

## Contrôle des documents

| Article | Détails |
|------|---------|
| Numéro d'identification du document | IRP-PORTFOLIO-001 |
| Version | 1.0 |
| Classement | Interne |
| Propriétaire | Pierre Durand (DevOps) |
| Dernière mise à jour | 2025-02-17 |

---

## 1. Objectif et portée

### 1.1 Objectif

Ce plan de réponse aux incidents (IRP) établit des procédures pour détecter, répondre et récupérer les incidents affectant la plateforme d'optimisation de portefeuille.

### 1.2 Portée

S'applique à tous les incidents affectant :
- Disponibilité du service API
- Opérations de pipeline de données
- Intégrité des données et qualité
- Failles de sécurité
- Défaillances d'infrastructure

### 1.3 Objectifs

1. Minimiser les interruptions de service
2. Protéger l'intégrité des données
3. Maintenir la communication avec les parties prenantes
4. Tirer des leçons des incidents pour éviter qu'ils ne se reproduisent

---

## 2. Classification des incidents

### 2.1 Niveaux de gravité

| Niveau | Nom | Définition | Exemples |
|-------|------|------------|----------|
| SEV-1 | Critique | Panne complète, violation de données, incident de sécurité | API en panne, corruption des données |
| SEV-2 | Majeur | Dégradation importante, panne partielle | Échec du pipeline, latence élevée |
| SEV-3 | Mineur | Impact limité, solution de contournement disponible | Erreur de point de terminaison unique |
| SEV-4 | Faible | Impact minimal, problèmes esthétiques | Problème d'interface utilisateur, avertissement de journal |

### 2.2 Matrice de classification

| Impact | Tous les utilisateurs | Certains utilisateurs | Utilisateur unique |
|--------|-----------|------------|-------------|
| **Service en panne** | SEV-1 | SEV-2 | SEV-3 |
| **Dégradé** | SEV-2 | SEV-3 | SEV-4 |
| **Inconvénient** | SEV-3 | SEV-4 | SEV-4 |

### 2.3 Délais de réponse

| Gravité | Détection | Réponse | Résolution | Communication |
|----------|-----------|----------|------------|---------------|
| SEV-1 | 5 minutes | 15 minutes | 4 heures | Toutes les 30 minutes |
| SEV-2 | 15 minutes | 1 heure | 8 heures | Toutes les 2 heures |
| SEV-3 | 1 heure | 4 heures | 24 heures | Quotidien |
| SEV-4 | 24 heures | Meilleur effort | Meilleur effort | Sur la résolution |

---

## 3. Équipe de réponse aux incidents

### 3.1 Rôles et responsabilités

| Rôle | Responsabilité | Primaire | Sauvegarde |
|------|----------------|---------|--------|
| Commandant des incidents | Coordination globale | Pierre Durand | Laien Wu |
| Responsable technique | Enquête et réparation | Laien Wu | Sophie Bernard |
| Communication | Mises à jour des parties prenantes | Lucas Petit | Marie Dupont |
| Scribe | Documents | Attribué au moment de l'exécution | - |

### 3.2 Coordonnées

| Rôle | Nom | Téléphone | E-mail |
|------|------|-------|-------|
| Primaire de garde | Rotation | +33 X XX XX XX XX | oncall@company.com |
| Responsable DevOps | Pierre Durand | +33 X XX XX XX XX | pierre@company.com |
| Ingénieur de données | Laien Wu | +33 X XX XX XX XX | data@company.com |
| CTO (escalade) | François Martin | +33 X XX XX XX XX | francois@company.com |

### 3.3 Chemin de remontée

```
┌─────────────────────────────────────────────────────────────────┐
│                      ESCALATION TIMELINE                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  0 min      On-Call Engineer alerted                            │
│     │                                                           │
│     │       ┌─ SEV-1: Immediate escalation to all               │
│     │       │                                                   │
│  15 min     ├─ SEV-2: Escalate to Tech Lead                     │
│     │       │                                                   │
│     │       └─ SEV-3/4: Continue solo                           │
│     │                                                           │
│  30 min     No progress → Escalate to next level                │
│     │                                                           │
│  1 hour     SEV-1/2: DevOps Lead joins                          │
│     │                                                           │
│  2 hours    SEV-1: CTO notified                                 │
│     │                                                           │
│  4 hours    SEV-1: All hands, business notified                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Phases de réponse aux incidents

### 4.1 Phase 1 : Détection

**Objectif :** Identifier qu'un incident est se produisant

**Sources :**
- Alertes de surveillance automatisées
- Échecs du contrôle de santé
- Rapports utilisateur
- Observation manuelle

**Actions :**
1. Accuser réception de l'alerte
2. Vérifier que l'incident est réel (pas de faux positif)
3. Recueillir les informations initiales
4. Classer la gravité

**Liste de contrôle de détection :**
```
☐ Alert received/incident reported
☐ Verified incident is genuine
☐ Initial scope assessed
☐ Severity classified
☐ Incident ticket created
```

### 4.2 Phase 2 : Triage

**Objectif :** Évaluer l'impact et mobiliser la réponse

**Actions :**
1. Créer un canal d'incident (Slack : #incident-YYYY-MM-DD)
2. Désigner le commandant de l'incident
3. Appelez des intervenants supplémentaires si nécessaire
4. Commencer l'évaluation d'impact

**Liste de contrôle de tri :**
```
☐ Incident Commander assigned
☐ Communication channel created
☐ Initial impact assessment complete
☐ Stakeholders notified (per severity)
☐ Response team assembled
```

### 4.3 Phase 3 : Confinement

**Objectif :** Prévenir d'autres dommages

**Actions :**
1. Isoler les composants concernés
2. Préserver les preuves (journaux, état)
3. Mettre en œuvre des solutions de contournement temporaires
4. Empêcher la propagation de l'incident

**Stratégies de confinement :**

| Type d'incident | Action de confinement |
|---------------|-------------------|
| Panne d'API | Redémarrer le conteneur, basculement |
| Corruption des données | Arrêter le pipeline, mettre les données en quarantaine |
| Faille de sécurité | Révoquer l'accès, isoler le système |
| Problème de performances | Faire évoluer les ressources, activer la mise en cache |

### 4.4 Phase 4 : Enquête

**Objectif :** Identifier la cause première

**Actions :**
1. Rassemblez les journaux et les métriques
2. Reconstruction de la chronologie
3. Test d'hypothèse
4. Identification de la cause première

**Commandes d'enquête :**
```bash
# Gather logs
docker compose logs --since="1h" > incident_logs.txt

# Check recent changes
git log --oneline -20

# Check system state
docker compose ps
docker stats --no-stream

# Check data state
ls -la data/raw/klines/
ls -la data/output/
```

### 4.5 Phase 5 : Résolution

**Objectif :** Restaurer le service normal

**Actions :**
1. Implémenter le correctif
2. Vérifiez le correctif dans la préparation (si disponible)
3. Déployer en production
4. Vérifiez le service restauré
5. Surveiller la récidive

**Liste de contrôle de résolution :**
```
☐ Fix identified
☐ Fix tested
☐ Fix deployed
☐ Service verified operational
☐ Monitoring shows normal
☐ Stakeholders notified of resolution
```

### 4.6 Phase 6 : Récupération

**Objectif :** Retour à des opérations entièrement normales

**Actions :**
1. Supprimez les solutions de contournement temporaires
2. Vérifier que tous les services sont opérationnels
3. Rattraper les opérations manquées (remblai de pipeline)
4. Confirmer l'intégrité des données

**Tâches de récupération :**
```bash
# Backfill missed pipeline runs
docker compose exec airflow-webserver airflow dags backfill \
  portfolio_optimization \
  --start-date 2025-01-15 \
  --end-date 2025-01-16

# Verify data integrity
docker compose exec api python -c "
from src.storage.duckdb import DuckDBStorage
with DuckDBStorage() as db:
    print(db.query('SELECT COUNT(*) AS rows FROM fact_prices'))
"
```

### 4.7 Phase 7 : Post-incident

**Objectif :** Apprendre et s'améliorer

**Actions :**
1. Planifier l'autopsie (dans les 48 heures)
2. Documenter le calendrier et les actions
3. Identifier les améliorations
4. Suivre les éléments d'action
5. Partager les enseignements

---

## 5. Modèles de communication

### 5.1 Notification initiale (SEV-1/2)

```
Subject: [INCIDENT] Portfolio Platform - {Brief Description}

Severity: SEV-{X}
Status: Investigating

Impact:
- {Description of user/service impact}

Timeline:
- {Time} - Incident detected
- {Time} - Investigation started

Current Actions:
- {What is being done}

Next Update: {Time}

Incident Commander: {Name}
```

### 5.2 Mise à jour du statut

```
Subject: [UPDATE] Portfolio Platform Incident - {Time}

Status: {Investigating/Identified/Fixing/Resolved}

Progress:
- {What we've learned}
- {What we've done}

Current Impact:
- {Updated impact assessment}

Next Steps:
- {Planned actions}

ETA: {If known, otherwise "TBD"}

Next Update: {Time}
```

### 5.3 Notification de résolution

```
Subject: [RESOLVED] Portfolio Platform Incident

Status: Resolved

Resolution:
- {What was the problem}
- {What was the fix}

Duration: {Start time} to {End time} ({X hours Y minutes})

Impact Summary:
- {Services affected}
- {Data affected, if any}

Follow-up:
- Post-mortem scheduled for {date/time}
- {Any ongoing monitoring}

Thank you for your patience.
```

---

## 6. Runbooks d'incidents

### L'API 6.1 ne répond pas

**Symptômes :** La vérification de l'état échoue, rapportent les utilisateurs erreurs

**Actions immédiates :**
```bash
# 1. Check container status
docker compose ps api

# 2. Check logs for errors
docker compose logs --tail=100 api

# 3. Restart container
docker compose restart api

# 4. If persists, recreate container
docker compose up -d --force-recreate api

# 5. Check resource constraints
docker stats api
```

**Agir si :** Le redémarrage n'aide pas, les journaux affichent des erreurs inconnues

### 6.2 Défaillance du pipeline

**Symptômes :** Le DAG du flux d'air indique un échec, aucune donnée update

**Actions immédiates :**
```bash
# 1. Check Airflow task logs
# Go to http://localhost:8081 → DAG → Failed task → Logs

# 2. Check which task failed
docker compose exec airflow-webserver airflow tasks list portfolio_optimization

# 3. Clear and retry failed task
docker compose exec airflow-webserver airflow tasks clear \
  portfolio_optimization -t ingest -s 2025-01-15

# 4. If data source issue, check external APIs
curl -s "https://api.binance.com/api/v3/ping"

# 5. Manual run of failed step
docker compose exec api python -c "
from src.pipeline import ingest_incremental
from src.storage import get_storage

storage = get_storage()
data = ingest_incremental()
storage.save_raw(data)
"
```

**Agir si :** Erreurs d'API, corruption de données détectée

### 6.3 Problème de qualité des données

**Symptômes :** Valeurs inattendues dans les réponses d'API, alertes

**Immédiat Actions :**
```bash
# 1. Stop further processing
# Pause Airflow DAG in UI

# 2. Identify bad data
docker compose exec api python -c "
from src.storage.duckdb import DuckDBStorage
with DuckDBStorage() as db:
    print(db.query('''
      SELECT symbol, MIN(close), MAX(close), COUNT(*) AS rows
      FROM fact_prices
      GROUP BY symbol
    '''))
"

# 3. Check source data
docker compose exec api python -c "
import pyarrow.parquet as pq
table = pq.read_table('data/raw/klines/BTCUSDT.parquet')
print(table.num_rows)
print(table.column_names)
"

# 4. If bad data found, quarantine
mv data/raw/klines/BTCUSDT.parquet data/quarantine/

# 5. Re-ingest from source
docker compose exec api python -c "
from src.pipeline.ingest import fetch_klines
from src.storage import get_storage

storage = get_storage()
records = fetch_klines('BTCUSDT', period_days=7)
storage.save_raw({'BTCUSDT': records})
"
```

**Agir si :** Source de corruption des données inconnue, plusieurs symboles affectés

### 6.4 Incident de sécurité

**Symptômes :** Accès non autorisé, activité suspecte

**Actions immédiates :**
```bash
# 1. IMMEDIATELY contain
docker compose stop  # Stop all services

# 2. Preserve evidence
cp -r logs/ incident_evidence/
docker compose logs > incident_evidence/docker_logs.txt
cp -r data/ incident_evidence/data_snapshot/

# 3. Revoke credentials
# Rotate all API keys, passwords

# 4. Notify security team
# Call security lead immediately

# 5. Do NOT:
# - Delete logs
# - Restart services without authorization
# - Communicate externally without approval
```

**Transmettre immédiatement à :** CTO, responsable de la sécurité

---

## 7. Examen post-incident

### 7.1 Modèle post-mortem

```markdown
# Post-Mortem: {Incident Title}

**Date:** {Incident Date}
**Duration:** {X hours Y minutes}
**Severity:** SEV-{X}
**Author:** {Name}
**Status:** {Draft/Final}

## Summary

{1-2 sentence summary of what happened}

## Impact

- Users affected: {number}
- Services affected: {list}
- Data affected: {yes/no, details}
- Revenue impact: {if applicable}

## Timeline

| Time (UTC) | Event |
|------------|-------|
| HH:MM | Incident started |
| HH:MM | Alert triggered |
| HH:MM | Response began |
| HH:MM | Root cause identified |
| HH:MM | Fix deployed |
| HH:MM | Service restored |

## Root Cause

{Detailed explanation of what caused the incident}

## Resolution

{What was done to fix the issue}

## What Went Well

- {Point 1}
- {Point 2}

## What Could Be Improved

- {Point 1}
- {Point 2}

## Action Items

| Action | Owner | Due Date | Status |
|--------|-------|----------|--------|
| {Action} | {Name} | {Date} | {Open/Done} |

## Lessons Learned

{Key takeaways for the team}
```

### 7.2 Réunion post-mortem

**Délai :** Dans les 48 heures suivant la résolution

**Participants :**
- Intervenants en cas d'incident
- Équipe responsables
- Parties prenantes concernées (facultatif)

**Ordre du jour :**
1. Examen du calendrier (15 minutes)
2. Discussion sur les causes profondes (15 min)
3. Ce qui s'est bien passé (10 min)
4. Ce qu'il faut améliorer (10 min)
5. Points d'action (10 minutes)

**Règles :**
- Culture irréprochable - se concentrer sur les systèmes et non sur les personnes
- Aucune interruption pendant l'examen du calendrier
- Toutes les voix entendues
- Points d'action concrets avec propriétaires

---

## 8. Formation et tests

### 8.1 Exigences de formation

| Rôle | Formation | Fréquence |
|------|----------|-----------|
| Tous les ingénieurs | Aperçu de l'IRP | Lors de l'adhésion, chaque année |
| Sur appel | Commandement des incidents | Trimestriel |
| Pistes | Communication | Annuellement |

### 8.2 Exercices d'intervention en cas d'incident

| Type de foret | Fréquence | Portée |
|------------|-----------|-------|
| Exercice sur table | Trimestriel | Discussion d'équipe |
| Test du Runbook | Mensuel | Exécuter des runbooks |
| Forage complet | Annuellement | Incident simulé |

### 8.3 Scénarios d'exercice

1. ** Panne de l'API : ** Le conteneur plante et doit être redémarré 
2. **Échec du pipeline :** L'API Binance renvoie des erreurs
3. **Corruption des données :** Données incorrectes dans la zone Or
4. **Sécurité :** Accès API non autorisé détecté

---

## 9. Historique des révisions

| Version | Dates | Auteur | Modifications |
|---------|------|--------|---------|
| 1.0 | 2025-02-17 | Pierre Durand | Version initiale |

---

*Ce plan est révisé et mis à jour tous les trimestres.*
*Dernier exercice effectué : N/A (nouveau plan)*
*Prochain exercice prévu : 2025-03-15*

