# Revue Sprint 2 - Traitement des données et API

**Date :** 03/02/2025
**Heure :** 14h00 - 15h30
**Sprint :** 2 (Traitement des données)

## Participants

| Nom | Rôle | Présent |
|------|------|---------|
| Marie Dupont | Propriétaire de produit | ✓ |
| Jean-Martin | Analyste d'affaires | ✓ |
| Laien Wu | Ingénieur de données | ✓ |
| Sophie Bernard | Analyste de données | ✓ |
| Pierre Durand | Ingénieur DevOps | ✓ |
| Lucas Petit | Maître Scrum | ✓ |
| Thomas Leroy | Sécurité informatique | ✓ (Invité) |

---

## Objectif de sprint

> Mettre en œuvre le calcul des mesures financières, l'entrepôt de données DuckDB et l'API REST.

**État de l'objectif :** ✅ ATTEINT

---

## Résumé de la démonstration

### 1. Calcul des mesures financières (Laien)

**Démontré :**
- Calcul des rendements logarithmiques : `r_t = ln(P_t / P_{t-1})`
- Volatilité annualisée : `σ × √365`
- Matrice de corrélation (Pearson)
- Matrice de covariance (annualisé)

**Exemple de résultat :**
```
Volatility:
  BTCUSDT: 45.2% annualized
  ETHUSDT: 52.8% annualized
  SOLUSDT: 78.3% annualized

Correlation Matrix:
         BTC    ETH    SOL
  BTC   1.00   0.85   0.72
  ETH   0.85   1.00   0.78
  SOL   0.72   0.78   1.00
```

**Validation :**
- Les calculs vérifiés par Sophie correspondent à la référence Excel (à 0,1 %)

### 2. DuckDB Data Warehouse (Laien)

**Démontré :**
- Schéma en étoile mise en œuvre
- `fact_prices` - Données OHLCV
- `dim_symbol` - Dimension de symbole
- `dim_date` - Dimension de date avec attributs de calendrier

**Requête SQL en direct :**
```sql
SELECT symbol, AVG(close) as avg_price, COUNT(*) as records
FROM fact_prices
GROUP BY symbol
ORDER BY avg_price DESC;
```

**Performance :** Requête sur 450 enregistrements en < 10 ms

### 3. API REST (Sophie)

**Démontré :**
- `GET /` - Santé check
- `GET /symbols` - Liste des symboles disponibles
- `GET /klines/BTCUSDT` - Obtenir l'historique des prix
- `GET /metrics` - Liste des métriques disponibles
- `GET /portfolio` - Obtenir les pondérations optimales

**OpenAPI Documentation :**
- Généré automatiquement à `/docs`
- Tous les points de terminaison documentés avec des exemples

**Temps de réponse :** Tous les points de terminaison < 200 ms

### 4. Déploiement de Docker (Pierre)

**Démontré :**
- Conteneur API exécuté sur le port 8000
- Benchmarks PostgreSQL sur le port 5433
- Le point de terminaison du contrôle de santé fonctionne
- Politique de redémarrage configuré

---

## User Stories terminées

| Identifiant de l'histoire | Titre | Points | Statut |
|----------|-------|--------|--------|
| US-003 | Calculer les mesures financières | 5 | ✅ Terminé |
| US-007 | API REST pour l'accès aux données | 5 | ✅ Terminé |
| US-008 | Interface de requête SQL | 5 | ✅ Terminé |

**Vitesse :** 15 points d'histoire (contre 13 dans le Sprint 1)

---

## Commentaires des parties prenantes

**Marie (PO):**
> "La démo de l'API était impressionnante. C'est exactement ce dont nous avons besoin pour l'intégration du tableau de bord."

**Jean (BA):**
> "La matrice de corrélation sera très utile pour l'analyse de diversification. Pouvons-nous exporter vers Excel?"

**Action :** Ajouter un point de terminaison d'exportation CSV dans Sprint 4

**Thomas (Sécurité) :**
> "L'API n'a actuellement aucune authentification. Est-ce acceptable ?"

**Discussion :**
- Portée MVP = pas d'authentification (usage interne uniquement)
- La production serait nécessaire Clés API ou OAuth
 – Documentée comme limitation connue

---

## Dette technique identifiée

| Article | Priorité | Sprint |
|------|----------|--------|
| Ajouter l'authentification API | Moyen | Post-MVP |
| Ajouter une limitation du taux de requête | Faible | Post-MVP |
| Améliorer les messages d'erreur | Faible | Sprint 4 |

---

## Aperçu de Sprint 3

**Objectif :** Mettre en œuvre l'optimisation de Markowitz et l'orchestration d'Airflow

**Stories prévues :**
- US-005 : Optimisation de Markowitz (8 pts)
- US-009 : Planification automatisée des pipelines (5 pts)

**Capacité :** 13 points

---

## Métriques

| Métrique | Sprint 1 | Sprint 2 | Tendance |
|--------|----------|----------|-------|
| Vitesse | 13 | 15 | ↑ |
| Bogues trouvés | 2 | 1 | ↓ |
| Éléments de dette technologique | 1 | 3 | ↑ |
| Couverture des tests | 0% | 15% | ↑ |

---

## Mise à jour des risques

| Risque | Statut | Remarques |
|------|--------|-------|
| Modifications de l'API Binance | Vert | Aucun problème |
| Qualité des données | Vert | Validation en cours |
| Chronologie | Vert | En bonne voie |
| Point de défaillance unique | Jaune | Besoin de suivi |

---

*Compte-rendu enregistré par : Lucas Petit*
*Sprint accepté par : Marie Dupont (Product Owner)*

