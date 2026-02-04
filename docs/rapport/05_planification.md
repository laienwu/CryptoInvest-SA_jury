# Planification et Supervision (C5, C6)

## 1. Composition de l'équipe

### 1.1 Équipe projet
| Rôle | Personne | Compétences |
|------|----------|-------------|
| Data Engineer | [Votre nom] | Python, SQL, Docker, ETL |
| Product Owner | (Simulé) | Définition besoin métier |
| Utilisateur final | (Simulé) | Validation fonctionnelle |

### 1.2 Budget
| Poste | Montant | Justification |
|-------|---------|---------------|
| Ressources humaines | 0€ | Projet certification |
| Infrastructure | 0€ | Local / Docker |
| Licences logicielles | 0€ | 100% open-source |
| **Total** | **0€** | - |

---

## 2. Feuille de route

### 2.1 Grandes étapes

```
PHASE 1: FONDATIONS (Semaines 1-2)
├── Setup environnement
├── Architecture storage
└── Pipeline ingest

PHASE 2: TRANSFORMATION (Semaines 3-4)
├── Module transform
├── Calculs statistiques
└── Tests unitaires

PHASE 3: ANALYTICS (Semaines 5-6)
├── DuckDB warehouse
├── Star schema
└── Requêtes SQL

PHASE 4: EXPOSITION (Semaines 7-8)
├── FastAPI endpoints
├── Documentation API
└── Docker packaging

PHASE 5: OPTIMISATION (Semaines 9-10)
├── Module Markowitz
├── Intégration pipeline
└── Tests end-to-end

PHASE 6: FINALISATION (Semaines 11-12)
├── Documentation
├── Rapport certification
└── Préparation soutenance
```

### 2.2 Diagramme de Gantt simplifié

```
Semaine    1  2  3  4  5  6  7  8  9  10 11 12
           ─────────────────────────────────────
Phase 1    ████
Phase 2          ████
Phase 3                ████
Phase 4                      ████
Phase 5                            ████
Phase 6                                  ████
           ─────────────────────────────────────
Jalons     J1       J2       J3       J4    J5
```

### 2.3 Jalons

| Jalon | Date | Livrable | Validation |
|-------|------|----------|------------|
| J1 | Sem 2 | Pipeline ingest fonctionnel | Données en raw/ |
| J2 | Sem 4 | Métriques calculées | Données en processed/ |
| J3 | Sem 6 | DWH opérationnel | Requêtes SQL OK |
| J4 | Sem 8 | API déployée | /docs accessible |
| J5 | Sem 12 | Projet complet | Soutenance ready |

---

## 3. Découpage en tâches

### 3.1 Phase 1 - Fondations

| ID | Tâche | Effort | Responsable | Dépendance |
|----|-------|--------|-------------|------------|
| 1.1 | Setup Git repo | 1h | DE | - |
| 1.2 | Config pyproject.toml | 1h | DE | 1.1 |
| 1.3 | Structure dossiers | 1h | DE | 1.1 |
| 1.4 | Interface Storage | 4h | DE | 1.3 |
| 1.5 | ParquetStorage | 8h | DE | 1.4 |
| 1.6 | Module ingest | 8h | DE | 1.5 |
| 1.7 | Tests ingest | 4h | DE | 1.6 |

### 3.2 Phase 2 - Transformation

| ID | Tâche | Effort | Responsable | Dépendance |
|----|-------|--------|-------------|------------|
| 2.1 | Calcul rendements | 4h | DE | 1.6 |
| 2.2 | Calcul volatilité | 2h | DE | 2.1 |
| 2.3 | Matrice corrélation | 4h | DE | 2.1 |
| 2.4 | Matrice covariance | 2h | DE | 2.3 |
| 2.5 | Tests transform | 4h | DE | 2.4 |

### 3.3 Phase 3 - Analytics

| ID | Tâche | Effort | Responsable | Dépendance |
|----|-------|--------|-------------|------------|
| 3.1 | DuckDBStorage | 8h | DE | 1.5 |
| 3.2 | Star schema views | 4h | DE | 3.1 |
| 3.3 | Requêtes analytiques | 4h | DE | 3.2 |
| 3.4 | Tests DuckDB | 2h | DE | 3.3 |

### 3.4 Phase 4 - Exposition

| ID | Tâche | Effort | Responsable | Dépendance |
|----|-------|--------|-------------|------------|
| 4.1 | Setup FastAPI | 2h | DE | - |
| 4.2 | Endpoints CRUD | 4h | DE | 4.1 |
| 4.3 | Documentation OpenAPI | 2h | DE | 4.2 |
| 4.4 | Dockerfile | 4h | DE | 4.2 |
| 4.5 | docker-compose | 2h | DE | 4.4 |

### 3.5 Phase 5 - Optimisation

| ID | Tâche | Effort | Responsable | Dépendance |
|----|-------|--------|-------------|------------|
| 5.1 | Algorithme Markowitz | 8h | DE | 2.4 |
| 5.2 | Intégration pipeline | 4h | DE | 5.1 |
| 5.3 | Tests end-to-end | 4h | DE | 5.2 |

### 3.6 Phase 6 - Finalisation

| ID | Tâche | Effort | Responsable | Dépendance |
|----|-------|--------|-------------|------------|
| 6.1 | Documentation technique | 8h | DE | 5.3 |
| 6.2 | Rapport certification | 16h | DE | 6.1 |
| 6.3 | Slides présentation | 8h | DE | 6.2 |
| 6.4 | Répétition soutenance | 4h | DE | 6.3 |

---

## 4. Estimation des efforts

### 4.1 Méthode de pondération
Estimation en heures avec méthode **Planning Poker** simplifiée :
- 1h = tâche triviale
- 2-4h = tâche simple
- 8h = tâche complexe
- 16h = tâche majeure

### 4.2 Récapitulatif

| Phase | Effort estimé | % du projet |
|-------|---------------|-------------|
| Fondations | 27h | 20% |
| Transformation | 16h | 12% |
| Analytics | 18h | 13% |
| Exposition | 14h | 10% |
| Optimisation | 16h | 12% |
| Finalisation | 36h | 27% |
| **Total** | **127h** | 100% |

---

## 5. Suivi et indicateurs

### 5.1 Indicateurs de suivi (KPIs)

| Indicateur | Cible | Mesure |
|------------|-------|--------|
| Tâches complétées | 100% | Checklist |
| Jalons respectés | 5/5 | Dates |
| Tests passants | 100% | CI/CD |
| Couverture code | >80% | Coverage |

### 5.2 Tableau de bord

```
AVANCEMENT PROJET
═══════════════════════════════════════════
Phase 1: Fondations      [████████████] 100%
Phase 2: Transformation  [████████████] 100%
Phase 3: Analytics       [████████████] 100%
Phase 4: Exposition      [████████████] 100%
Phase 5: Optimisation    [████████████] 100%
Phase 6: Finalisation    [████████░░░░]  70%
═══════════════════════════════════════════
GLOBAL                   [██████████░░]  95%
```

### 5.3 Rituels de suivi
| Rituel | Fréquence | Durée | Objectif |
|--------|-----------|-------|----------|
| Daily standup | Quotidien | 5min | Blocages |
| Weekly review | Hebdo | 30min | Avancement |
| Sprint review | Bi-mensuel | 1h | Démo |

---

## 6. Gestion des risques

### 6.1 Registre des risques

| Risque | Proba | Impact | Mitigation |
|--------|-------|--------|------------|
| API Binance down | Faible | Moyen | Cache local, retry |
| Retard Phase 5 | Moyen | Haut | Buffer 1 semaine |
| Bug bloquant | Moyen | Moyen | Tests, code review |
| Maladie | Faible | Haut | Documentation |

### 6.2 Plan de contingence
- **Retard > 1 semaine** : Réduire scope Phase 6 (moins de slides)
- **Bug critique** : Rollback version précédente
- **API indisponible** : Utiliser données en cache

---

## 7. Communication

### 7.1 Parties prenantes
| Partie | Intérêt | Communication |
|--------|---------|---------------|
| Jury certification | Évaluation | Rapport + soutenance |
| Formateur | Suivi | Points hebdo |
| (Client simulé) | Résultats | Démo |

### 7.2 Livrables de communication
| Livrable | Destinataire | Format |
|----------|--------------|--------|
| Rapport professionnel | Jury | PDF/Markdown |
| Documentation technique | Jury | Markdown |
| Slides soutenance | Jury | PPT/PDF |
| README | Utilisateurs | Markdown |
