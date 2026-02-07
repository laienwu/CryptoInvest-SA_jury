# Accord de niveau de service (SLA)

## Informations sur le document

| Article | Détails |
|------|---------|
| Numéro d'identification du document | SLA-PORTFOLIO-001 |
| Version | 1.0 |
| Date d'entrée en vigueur | 2025-02-28 |
| Date de révision | 2025-08-28 |
| Propriétaire | Pierre Durand (DevOps) |
| Approbateur | François Martin (CTO) |

---

## 1. Description du service

### 1.1 Présentation

La plateforme d'optimisation de portefeuille fournit des services automatisés d'analyse et d'optimisation de portefeuille de cryptomonnaies. La plateforme se compose de :

- **Data Pipeline** : collecte et traitement quotidiens automatisés des données
- **API REST** : accès aux données et recommandations de portefeuille
- **Airflow Dashboard** : surveillance et gestion du pipeline

### 1.2 Service Horaires

| Composant | Fenêtre de disponibilité |
|-----------|---------------------|
| API REST | 24h/24 et 7j/7 |
| Pipeline de données | Tous les jours de 00h00 à 01h00 UTC |
| Tableau de bord du flux d'air | 24h/24 et 7j/7 (au mieux) |
| Assistance | Heures d'ouverture (09h00-18h00 CET) |

---

## 2. Objectifs de niveau de service (SLO)

### 2.1 Disponibilité

| Services | Cible | Période de mesure | Calcul |
|---------|--------|-------------------|-------------|
| API REST | 99,5% | Mensuel | Temps de disponibilité/Durée totale |
| Pipeline de données | 99,0% | Mensuel | Exécutions réussies/Exécutions planifiées |
| Tableau de bord du flux d'air | 99,0% | Mensuel | Disponibilité / Durée totale |

**Exclusions du calcul de disponibilité :**
- Fenêtres de maintenance planifiées (annoncées 48h à l'avance)
- Pannes d'API externes (Binance, CoinGecko)
- Force majeure événements

### 2.2 Performances

| Métrique | Cible | Centile |
|--------|--------|------------|
| Temps de réponse API | < 200 ms | p50 |
| Temps de réponse API | < 500 ms | p95 |
| Temps de réponse API | < 1000 ms | p99 |
| Temps d'exécution du pipeline | < 5 minutes | p95 |

### 2.3 Qualité des données

| Métrique | Cible |
|--------|--------|
| Fraîcheur des données | < 24 heures |
| Complétude des données | > 99 % (valeurs non nulles) |
| Exactitude des données | Validé par rapport à la source |

### 2.4 Temps de réponse du support

| Priorité | Réponse initiale | Objectif de résolution |
|----------|-----------------|-------------------|
| P1 - Critique | 15 minutes | 4 heures |
| P2 - Élevé | 1 heure | 8 heures |
| P3 - Moyen | 4 heures | 24 heures |
| P4 - Faible | 24 heures | Meilleur effort |

---

## 3. Définitions des priorités

### P1 – Critique

**Définition :** Panne complète du service affectant tous les utilisateurs, corruption des données ou sécurité incident.

**Exemples :**
- L'API renvoie des erreurs 5xx pour toutes les demandes
- Le pipeline produit des données incorrectes
- Faille de sécurité détectée

**Réponse :**
- Immédiate escalade vers un ingénieur de garde
- Page d'état mise à jour dans les 15 minutes
- Tout le monde sur le pont jusqu'à résolution

### P2 - Élevé

**Définition :** Fonctionnalité majeure altérée, dégradation significative des performances ou des données retards.

**Exemples :**
- Temps de réponse de l'API > 2 secondes
- Temps d'exécution du pipeline > 30 minutes
- Données non mises à jour depuis > 24 heures

**Réponse :**
- Attribué à un ingénieur disponible
- Page d'état mise à jour si elle est destinée au client
- Résolu dans un délai d'un jour ouvrable

### P3 - Moyen

**Définition :** Fonctionnalité mineure altérée, dégradation partielle du service, améliorations non urgentes.

**Exemples :**
- Un point de terminaison unique renvoie des erreurs
- Chargement lent du tableau de bord
- Alerte non critique tir

**Réponse :**
- Ajouté au backlog du sprint
- Traité dans le cadre du cycle de développement normal

### P4 - Faible

**Définition :** Problèmes esthétiques, fonctionnalité demandes, mises à jour de la documentation.

**Exemples :**
- Améliorations de l'interface utilisateur
- Lacunes dans la documentation
- Modifications mineures de la configuration

**Réponse :**
- Suivi dans le backlog
- Adressé dans la mesure où la capacité le permet

---

## 4. Fenêtres de maintenance

### 4.1 Maintenance planifiée

| Tapez | Fréquence | Durée | Avis |
|------|-----------|----------|--------|
| Correctifs de sécurité | Au besoin | < 30 minutes | 24 heures |
| Mises à jour mineures | Hebdomadaire | < 15 minutes | 48 heures |
| Mises à jour majeures | Mensuel | < 2 heures | 1 semaine |
| Infrastructures | Trimestriel | < 4 heures | 2 semaines |

### 4.2 Notification de maintenance

Les fenêtres de maintenance seront communiquées via :
- E-mail aux parties prenantes enregistrées
- Canal Slack (#portfolio-platform)
- Page d'état mise à jour

### 4.3 Maintenance d'urgence

En cas de vulnérabilité de sécurité ou de bug critique :
- Préavis minimum d'une heure lorsque cela est possible
- Action immédiate en cas de vulnérabilité zero-day
- Rapport post-incident dans les 24 heures heures

---

## 5. Gestion des incidents

### 5.1 Matrice de gravité des incidents

| Impact → | Élevé | Moyen | Faible |
|----------|------|--------|-----|
| **Tous les utilisateurs** | P1 | P2 | P3 |
| **Certains utilisateurs** | P2 | P3 | P4 |
| **Utilisateur unique** | P3 | P4 | P4 |

### 5.2 Communication des incidents

| Gravité | Mise à jour initiale | Mises à jour continues | Post-incident |
|----------|----------------|-----------------|---------------|
| P1 | 15 minutes | Toutes les 30 minutes | Dans les 24h |
| P2 | 1 heure | Toutes les 2 heures | Sous 48h |
| P3 | 4 heures | Quotidien | Dans un délai d'une semaine |
| P4 | Tel que résolu | N/A | N/A |

### 5.3 Chemin de remontée

```
┌─────────────────────────────────────────────────────────────────┐
│                      ESCALATION PATH                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  [L1] On-Call Engineer                                          │
│        │                                                         │
│        │ 30 min                                                  │
│        ▼                                                         │
│  [L2] Data Engineering Team Lead                                │
│        │                                                         │
│        │ 1 hour                                                  │
│        ▼                                                         │
│  [L3] DevOps Manager (Pierre)                                   │
│        │                                                         │
│        │ 2 hours                                                 │
│        ▼                                                         │
│  [L4] CTO (François)                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Crédits de service

### 6.1 Calcul du crédit

Si la disponibilité mensuelle tombe en dessous du SLO :

| Disponibilité | Crédit de service |
|--------------|----------------|
| 99.0% - 99.5% | 10% |
| 95.0% - 99.0% | 25% |
| < 95.0% | 50% |

*Remarque : Pour les projets internes, les crédits sont notionnels (priorité d'allocation des ressources)*

### 6.2 Exclusions de crédits

Les crédits ne s'appliquent pas lorsque la panne est causée par :
- Erreur de l'utilisateur ou une mauvaise configuration
- Dépendances externes (panne de l'API Binance)
- Maintenance planifiée
- Force majeure

---

## 7. Rapports

### 7.1 Rapports mensuels

Livrés le 5 de chaque mois :
- Mesures de disponibilité (% de disponibilité)
- Mesures de performances (centiles de latence)
- Incident résumé
- Journal de maintenance

### 7.2 Examens trimestriels

Planifié avec les parties prenantes :
- Examen de la conformité aux SLA
- Analyse des tendances
- Amélioration recommandations
- Propositions d'ajustement des SLA

---

## 8. Dépendances et hypothèses

### 8.1 Externe Dépendances

| Dépendance | ANS | Repli |
|------------|-----|----------|
| API Binance | Meilleur effort | Données mises en cache, alerte manuelle |
| CoinGecko | Meilleur effort | Méthode de scraping de secours |
| Centre Docker | Meilleur effort | Cache d'images local |
| Hébergement cloud | 99,9% | N/A (SLA du fournisseur d'hébergement) |

### 8.2 Hypothèses

- La connectivité réseau entre les composants est fiable
- Des ressources de calcul suffisantes sont allouées
- Les correctifs de sécurité sont appliqués dans les fenêtres de maintenance
- L'équipe dispose d'un capacité d'assistance

---

## 9. Accord et signatures

### 9.1 Fournisseur de services

| Rôle | Nom | Signature | Date |
|------|------|-----------|------|
| Responsable DevOps | Pierre Durand | ____________ | ______ |
| Ingénieur de données | Laien Wu | ____________ | ______ |

### 9.2 Consommateur de services

| Rôle | Nom | Signature | Date |
|------|------|-----------|------|
| Propriétaire de produit | Marie Dupont | ____________ | ______ |
| CTO (approbateur) | François Martin | ____________ | ______ |

---

## 10. Historique des révisions

| Version | Dates | Auteur | Modifications |
|---------|------|--------|---------|
| 1.0 | 2025-02-17 | Pierre Durand | Version initiale |

---

*Ce SLA est soumis à un examen annuel et peut être mis à jour avec un préavis de 30 jours.*

