# Matrice RACI - Projet d'optimisation de portefeuille

## Membres de l'équipe

| Rôle | Nom | Département |
|------|------|------------|
| **PO** | Propriétaire de produit | Affaires |
| **BA** | Analyste d'affaires | Affaires |
| **DE** | Ingénieur de données | Développement |
| **DA** | Analyste de données | Développement |
| **DevOps** | Ingénieur DevOps | Opérations informatiques |
| **SM** | Maître Scrum | Gestion de projet |

---

## Légende RACI

| Lettre | Signification | Description |
|--------|---------|-------------|
| **R**  | Responsable | Fait le travail |
| **A**  | Responsable | Décideur final, un seul par tâche |
| **C**  | Consulté | Fournit des commentaires avant la décision |
| **I** | Informé | Notifié après décision |

---

## Phases du projet

### Phase 1 : Initiation et planification

| Activité | PO | BA | DE | DA | DevOps | SM |
|----------|----|----|----|----|----|----|
| Définir les besoins métiers | A  | R | C | C | I | I |
| Entretiens avec les parties prenantes | C  | R | I | I | I | I |
| Approbation de la charte du projet | A | R | I | I | I | C |
| Etude de faisabilité technique | C  | I | R | C | C | I |
| Allocation des ressources | A | I | C | C | C | R |
| Planification des sprints | C  | C | R | R | R | A |

### Phase 2 : Collecte de données (Bloc 2)

| Activité | PO | BA | DE | DA | DevOps | SM |
|----------|----|----|----|----|----|----|
| Intégration API (Binance) | I | I | R | C | I | I |
| Ingestion multi-sources | I | C | R | C | I | I |
| Règles de qualité des données | C | R | A | C | I | I |
| Architecture de stockage | I | I | A | C | C | I |
| Création de base de données (MERISE) | I | C | R | C | I | I |
| Développement d'API REST | I | C | R | I | C | I |

### Phase 3 : Entrepôt de données (Bloc 3)

| Activité | PO | BA | DE | DA | DevOps | SM |
|----------|----|----|----|----|----|----|
| Modélisation du schéma en étoile | I | C | R | A | I | I |
| Implémentation de DuckDB | I | I | R | C | I | I |
| Développement de pipelines ETL | I | I | R | C | C | I |
| Création d'un DAG de flux d'air | I | I | R | I | C | I |
| Implémentation SCD | I | I | R | C | I | I |
| Test DWH | I | C | R | R | I | I |

### Phase 4 : Data Lake (Bloc 4)

| Activité | PO | BA | DE | DA | DevOps | SM |
|----------|----|----|----|----|----|----|
| Conception d'architecture lacustre | I | C | A | C | C | I |
| Infrastructure Docker | I | I | C | I | R | I |
| Création de catalogue de données | I | C | R | A | I | I |
| Conformité RGPD | A | R | C | C | C | I |
| Règles de gouvernance | A | R | C | C | C | I |

### Phase 5 : Déploiement et opérations

| Activité | PO | BA | DE | DA | DevOps | SM |
|----------|----|----|----|----|----|---|
| Configuration de l'environnement | I | I | C | I | R | I |
| Procédures de déploiement | I | I | C | I | A | I |
| Configuration de la surveillance | I | I | C | I | R | I |
| Définition SLA | A | C | C | I | R | I |
| Revue documentaire | C | C | R | R | R | A |
| Formation des utilisateurs | C | R | C | C | I | I |

### Phase 6 : Clôture du projet

| Activité | PO | BA | DE | DA | DevOps | SM |
|----------|----|----|----|----|----|---|
| Démo finale | A | R | R | R | R | C |
| Rétrospective | C | C | R | R | R | A |
| Transfert de connaissances | I | C | R | R | R | I |
| Approbation du projet | A | C | I | I | I | R |

---

## Matrice de communication

| Partie prenante | Type de communication | Fréquence | Propriétaire |
|-------------|-------------------|-----------|-------|
| Propriétaire de produit | Revue de sprint | Bihebdomadaire | SM |
| Analystes d'affaires | Examen des exigences | Hebdomadaire | BA |
| Équipe de développement | Stand-up quotidien | Quotidien | SM |
| Opérations informatiques | Planification du déploiement | Par version | DevOps |
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
