# Témoignages d'utilisateurs - Plateforme d'optimisation de portefeuille

## Epic 1 : Collecte de données

### US-001 : Collecte automatisée des prix
**En tant que** Gestionnaire de portefeuille
**Je souhaite** que le système collecte automatiquement les cryptomonnaies quotidiennes prix
**Pour que** je n'aie pas à télécharger manuellement les données des échanges

**Critères d'acceptation :**
- [ ] Le système récupère les données OHLCV de l'API Binance
- [ ] Les données sont collectées pour au moins 5 actifs cryptographiques
- [ ] La collecte s'exécute quotidiennement sans intervention manuelle
- [ ] Les collectes échouées déclenchent une alerte
- [ ] Les données historiques couvrent au minimum 90 jours

**Priorité :** Élevée
**Points d'histoire :** 5
**Sprint :** 1

---

### US-002 : Intégration de données multi-sources
**En tant qu'** ingénieur de données
**Je souhaite** collecter des données à partir de plusieurs types de sources
**Afin que** nous ayons une redondance et un enrichissement ensembles de données

**Critères d'acceptation :**
- [ ] Lectures du système à partir de l'API REST (Binance)
- [ ] Lectures du système à partir de fichiers CSV (métadonnées)
- [ ] Lectures du système à partir de la configuration JSON
- [ ] Système récupère les données Web (classements du marché)
- [ ] Requêtes système PostgreSQL (benchmarks)
- [ ] Toutes les sources sont documentées

**Priorité :** Élevée
**Points d'histoire :** 8
**Sprint :** 2

---

## Epic 2 : Traitement des données

### US-003 : Calculer des indicateurs financiers
**En tant qu'analyste quantitatif
**Je veux** le système pour calculer les rendements, la volatilité et les corrélations
**Afin que** je puisse analyser la performance des actifs

**Critères d'acceptation :**
- [ ] Rendement journalier quotidien calculé pour tous les actifs
- [ ] Volatilité annualisée calculée (252 jours de bourse)
- [ ] Matrice de corrélation générée
- [ ] Matrice de covariance générée
- [ ] Les calculs correspondent à la validation Excel (±0,1 %)

**Priorité :** Élevée
**Points d'histoire :** 5
**Sprint :** 2

---

### US-004 : Validation de la qualité des données
**En tant qu'** ingénieur de données
**Je souhaite** des contrôles automatisés de la qualité des données
**Pour que** de mauvaises données ne corrompent pas notre analyse

**Critères d'acceptation :**
- [ ] Vérifier les valeurs nulles dans les données de prix
- [ ] Valider la continuité des prix (pas d'écart > 3 jours)
- [ ] Alerte sur les changements de prix anormaux (> 50 % quotidiennement)
- [ ] Consigner tous les résultats de validation
- [ ] Mettre en quarantaine les enregistrements invalides

**Priorité :** Moyenne
**Points d'histoire :** 3
**Sprint :** 3

---

## Epic 3 : Optimisation de portefeuille

### US-005 : Optimisation de Markowitz
**En tant que** gestionnaire de portefeuille
**Je veux** un niveau optimal pondérations de portefeuille calculées
**Afin que** je puisse maximiser les rendements ajustés au risque

**Critères d'acceptation :**
- [ ] Implémente une optimisation de la variance moyenne
- [ ] Maximise le ratio de Sharpe
- [ ] Respecte les contraintes : la somme des pondérations est de 1, pas de vente à découvert
-[ ] Résultats : pondérations, rendement attendu, volatilité, ratio de Sharpe
- [ ] Comparé à l'indice de référence de pondération égale

**Priorité :** Élevée
**Points de l'histoire :** 8
**Sprint :** 3

---

### US-006 : Configuration des contraintes
**En tant que** gestionnaire de risques
**Je souhaite** configurer les contraintes de portefeuille
**Pour que** l'optimisation respecte notre risque politiques

**Critères d'acceptation :**
- [ ] Poids maximum configurable par actif (40 % par défaut)
- [ ] Limites de concentration sectorielle configurables
- [ ] Option d'exclusion des pièces stables
- [ ] Contraintes stockées dans la configuration file
- [ ] Validation de la faisabilité des contraintes

**Priorité :** Moyenne
**Points d'histoire :** 3
**Sprint :** 4

---

## Epic 4 : accès aux données

### US-007 : API REST pour l'accès aux données
**En tant que** développeur frontend
**Je veux** un API REST pour accéder aux données du portefeuille
**Pour que** je puisse créer des tableaux de bord et des rapports

**Critères d'acceptation :**
- [ ] GET /symbols - liste des symboles disponibles
- [ ] GET /klines/{symbol} - obtenir l'historique des prix
- [ ] GET /metrics - liste les métriques disponibles
- [ ] GET /portfolio - obtient les pondérations optimales
- [ ] L'API renvoie JSON avec les codes d'erreur appropriés
- [ ] Temps de réponse < 500 ms pour tous les points de terminaison

**Priorité :** Élevée
**Points d'histoire :** 5
**Sprint :** 2

---

### US-008 : Interface de requête SQL
**En tant qu'analyste de données
**Je souhaite** interroger des données à l'aide de SQL
**Afin que** je puisse faire des tâches ponctuelles analyse

**Critères d'acceptation :**
- [ ] DuckDB fournit une interface SQL
- [ ] Schéma en étoile avec fact_prices, dim_symbol, dim_date
- [ ] Vues prédéfinies pour les requêtes courantes
- [ ] Performances des requêtes < 1 seconde pour 1 million de lignes
- [ ] Documentation des tables/vues disponibles

**Priorité :** Moyenne
**Points d'histoire :** 5
**Sprint :** 3

---

## Epic 5 : Opérations

### US-009 : Planification automatisée des pipelines
**En tant qu**ingénieur des opérations
**Je veux** l'ETL le pipeline doit s'exécuter selon un calendrier
**Pour que** les données soient toujours à jour

**Critères d'acceptation :**
- [ ] Le DAG Airflow s'exécute quotidiennement à 00h00 UTC
- [ ] Étapes du pipeline : ingérer → transformer → optimiser
- [ ] Les tâches ayant échoué réessayent automatiquement (maximum 3 fois)
- [ ] Notifications de réussite/échec
- [ ] Historique d'exécution visible dans l'interface utilisateur d'Airflow

**Priorité :** Élevée
**Points d'histoire :** 5
**Sprint :** 3

---

### US-010 : Surveillance et alertes
**En tant qu'**ingénieur des opérations
**Je souhaite** une surveillance de l'état du système
**Donc que** Je suis alerté lorsque quelque chose échoue

**Critères d'acceptation :**
- [ ] Le point de terminaison d'intégrité de l'API renvoie l'état
- [ ] Agrégation de journaux pour tous les composants
- [ ] Alerte en cas d'échec du pipeline
- [ ] Alerte en cas d'arrêt de l'API > 5 minutes
- [ ] Tableau de bord affichant les métriques du système

**Priorité :** Moyenne
**Points d'histoire :** 5
**Sprint :** 4

---

## Résumé de la Story Map

| Épique | Histoires | Total des points | Sprint |
|------|---------|--------------|--------|
| Collecte de données | US-001, US-002 | 13 | 1-2 |
| Traitement des données | US-003, US-004 | 8 | 2-3 |
| Optimisation du portefeuille | US-005, US-006 | 11 | 3-4 |
| Accès aux données | US-007, US-008 | 10 | 2-3 |
| Opérations | US-009, US-010 | 10 | 3-4 |
| **Total** | **10 histoires** | **52 points** | **4 sprints** |

---

## Définition de Terminé (DoD)

Une histoire est considérée comme « Terminée » lorsque :
- [ ] Le code est écrit et suit le codage normes
- [ ] Les tests unitaires sont réussis (le cas échéant)
- [ ] Le code est examiné par au moins un membre de l'équipe
- [ ] La documentation est mise à jour
- [ ] La fonctionnalité est déployée dans un environnement de test
- [ ] Le propriétaire du produit a accepté l'histoire
