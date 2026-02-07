# Matrice RACI - Projet d'optimisation de portefeuille

## Membres de l'équipe

| Rôle | Nom | Département |
|------|------|------------|
| **PO** | Propriétaire de produit | Affaires |
| **BA** | Analyste d'affaires | Affaires |
| **DE** | Ingénieur de données | Développement |
| **DA** | Analyste de données | Développement |
| **FAIRE** | Ingénieur DevOps | Opérations informatiques |
| **SM** | Maître Scrum | Gestion de projet |

---

## Légende RACI

| Lettre | Signification | Description |
|--------|---------|-------------|
| **R** | Responsable | Fait le travail |
| **A** | Responsable | Décideur final, un seul par tâche |
| **C** | Consulté | Fournit des commentaires avant la décision |
| **Je** | Informé | Notifié après décision |

---

## Phases du projet

### Phase 1 : Initiation et planification

| Activité | PO | BA | DE | DA | FAIRE | SM |
|----------|----|----|----|----|----|----|
| Définir les besoins métiers | Un | R | C | C | Je | Je |
| Entretiens avec les parties prenantes | C | R | Je | Je | Je | Je |
| Approbation de la charte du projet | Un | R | Je | Je | Je | C |
| Etude de faisabilité technique | C | Je | R | C | C | Je |
| Allocation des ressources | Un | Je | C | C | C | R |
| Planification des sprints | C | C | R | R | R | A |

### Phase 2 : Collecte de données (Bloc 2)

| Activité | PO | BA | DE | DA | FAIRE | SM |
|----------|----|----|----|----|----|----|
| Intégration API (Binance) | Je | Je | R | C | Je | Je |
| Ingestion multi-sources | Je | C | R | C | Je | Je |
| Règles de qualité des données | C | R | Un | C | Je | Je |
| Architecture de stockage | Je | Je | Un | C | C | Je |
| Création de base de données (MERISE) | Je | C | R | C | Je | Je |
| Développement d'API REST | Je | C | R | Je | C | I |

### Phase 3 : Entrepôt de données (Bloc 3)

| Activité | PO | BA | DE | DA | FAIRE | SM |
|----------|----|----|----|----|----|----|
| Modélisation du schéma en étoile | Je | C | R | Un | Je | Je |
| Implémentation de DuckDB | Je | Je | R | C | Je | Je |
| Développement de pipelines ETL | Je | Je | R | C | C | Je |
| Création d'un DAG de flux d'air | Je | Je | R | Je | C | Je |
| Implémentation SCD | Je | Je | R | C | Je | Je |
| Test DWH | Je | C | R | R | Je | I |

### Phase 4 : Data Lake (Bloc 4)

| Activité | PO | BA | DE | DA | FAIRE | SM |
|----------|----|----|----|----|----|----|
| Conception d'architecture lacustre | Je | C | Un | C | C | Je |
| Infrastructure Docker | Je | Je | C | Je | R | Je |
| Création de catalogue de données | Je | C | R | Un | Je | Je |
| Conformité RGPD | Un | R | C | C | C | Je |
| Règles de gouvernance | Un | R | C | C | C | I |

### Phase 5 : Déploiement et opérations

| Activité | PO | BA | DE | DA | FAIRE | SM |
|----------|----|----|----|----|----|----|
| Configuration de l'environnement | Je | Je | C | Je | R | Je |
| Procédures de déploiement | Je | Je | C | Je | Un | Je |
| Configuration de la surveillance | Je | Je | C | Je | R | Je |
| Définition SLA | Un | C | C | Je | R | Je |
| Revue documentaire | C | C | R | R | R | UNE |
| Formation des utilisateurs | C | R | C | C | Je | I |

### Phase 6 : Clôture du projet

| Activité | PO | BA | DE | DA | FAIRE | SM |
|----------|----|----|----|----|----|----|
| Démo finale | Un | R | R | R | R | C |
| Rétrospective | C | C | R | R | R | UNE |
| Transfert de connaissances | Je | C | R | R | R | Je |
| Approbation du projet | Un | C | Je | Je | Je | R |

---

## Matrice de communication

| Partie prenante | Type de communication | Fréquence | Propriétaire |
|-------------|-------------------|-----------|-------|
| Propriétaire de produit | Revue de sprint | Bihebdomadaire | SM |
| Analystes d'affaires | Examen des exigences | Hebdomadaire | BA |
| Équipe de développement | Stand-up quotidien | Quotidien | SM |
| Opérations informatiques | Planification du déploiement | Par version | FAIRE |
| Toutes les parties prenantes | Rapport de situation | Hebdomadaire | SM |
| Gestion | Comité directeur | Mensuel | PO |

---

## Chemin de remontée

```
Level 1: Team Member → Scrum Master
    ↓
Level 2: Scrum Master → Product Owner
    ↓
Level 3: Product Owner → Steering Committee
    ↓
Level 4: Steering Committee → Executive Sponsor
```

---

## Matrice d'approbation

| Type de décision | Approbateur | Sauvegarde |
|---------------|----------|--------|
| Changement de périmètre | Propriétaire de produit | Comité directeur |
| Architecture technique | Ingénieur de données | Responsable technique |
| Allocation budgétaire | Propriétaire de produit | Finances |
| Mise en ligne | Product Owner + DevOps | Comité directeur |
| Exception de sécurité | Sécurité informatique | Directeur technique |
