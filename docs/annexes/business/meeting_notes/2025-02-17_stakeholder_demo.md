# Démo des parties prenantes - MVP de l'optimisation du portefeuille

**Date :** 2025-02-17
**Heure :** 15h00 - 16h30
**Type :** Démo exécutive

## Participants

| Nom | Rôle | Département |
|------|------|------------|
| François Martin | Directeur technique | Exécutif |
| Marie Dupont | Propriétaire de produit | Affaires |
| Claire Rousseau | Responsable du commerce | Affaires |
| Jean-Martin | Analyste d'affaires | Affaires |
| Laien Wu | Ingénieur de données | Développement |
| Sophie Bernard | Analyste de données | Développement |
| Pierre Durand | Ingénieur DevOps | Opérations informatiques |
| Lucas Petit | Maître Scrum | PMO |

---

## Résumé

Le MVP de la plateforme d'optimisation de portefeuille est **fonctionnalité complète** et prêt pour les tests d'acceptation des utilisateurs. Le système automatise la collecte de données, l'analyse et l'optimisation de portefeuille pour les investissements en crypto-monnaie.

**Réalisation clé :** Pipeline de bout en bout exécuté quotidiennement avec un temps d'exécution < 5 minutes.

---

## Démo Ordre du jour

1. Aperçu de la valeur commerciale (5 min)
2. Démo du système en direct (30 min)
3. Architecture technique (10 min)
4. Conformité à la certification (10 minutes)
5. Feuille de route et prochaines étapes (10 min)
6. Questions et réponses (25 min)

---

## 1. Aperçu de la valeur commerciale (Marie)

### Énoncé du problème
- Collecte manuelle de données : 2 heures/jour
- Basé sur Excel analyse : sujette aux erreurs, non évolutive
- Aucune optimisation systématique : décisions instinctives

### Solution fournie
- Pipeline de données quotidien automatisé
- Optimisation de portefeuille de qualité professionnelle
- API pour l'intégration avec le trading systèmes

### Projection du retour sur investissement

| Métrique | Avant | Après | Amélioration |
|--------|--------|-------|-------------|
| Temps de collecte des données | 2h/jour | 0h/jour | -100 % |
| Temps d'analyse | 1h/jour | 5 min/jour | -92% |
| Fraîcheur des données | J+1 jour | T+0 | En temps réel |
| Portefeuille Sharpe | ~0,5 | ~1.2 | +140 % |

---

## 2. Démo du système en direct (Laien Wu)

### Démo Flow

**Étape 1 : Ingestion de données**
```
$ python -c "from src.pipeline import ingest_all_sources; ingest_all_sources()"

==================================================
MULTI-SOURCE INGESTION (C8) - 5 Source Types
==================================================

[Source 1/5] CSV File ✓
[Source 2/5] JSON File ✓
[Source 3/5] REST API ✓
[Source 4/5] Web Scraping ✓
[Source 5/5] PostgreSQL ✓

Sources loaded: 5/5
```

**Réaction des parties prenantes :** Claire impressionnée par la capacité multi-sources

**Étape 2 : Transformation des données**
```
$ python -c "from src.pipeline import transform_data; transform_data()"

Calculating volatility...
  BTCUSDT: 45.23% annualized
  ETHUSDT: 52.81% annualized
  ...

Correlation Matrix computed.
Covariance Matrix computed.
```

**Étape 3 : Optimisation du portefeuille**
```
$ python -c "from src.pipeline import optimize_portfolio; optimize_portfolio()"

==================================================
OPTIMAL PORTFOLIO
==================================================

Weights:
  BTCUSDT: 35.2%
  ETHUSDT: 24.8%
  BNBUSDT: 18.5%
  SOLUSDT: 12.3%
  ADAUSDT:  9.2%

Expected Return: 18.5%
Volatility:      28.3%
Sharpe Ratio:    1.24

Method: scipy (SLSQP optimization)
```

**François (CTO) :** "Quel est le ratio de Sharpe à pondération égale ?"
**Réponse :** "0,89 - notre optimisation l'améliore de 39 %"

**Étape 4 : Démo de l'API**
 - Affichage de l'interface utilisateur Swagger à `http://localhost:8000/docs`
- Appels en direct vers `/symbols`, `/klines/BTCUSDT`, `/portfolio`
- Temps de réponse tous < 200 ms

**Étape 5 : DAG de flux d'air**
- DAG affiché visualisation
- Planning quotidien à 00:00 UTC
- Dépendances des tâches : ingérer → transformer → optimiser

---

## 3. Architecture technique (Pierre)

```
┌─────────────────────────────────────────────────────────────┐
│                    DATA SOURCES (C8)                        │
│  [Binance API] [CSV] [JSON] [Web Scraping] [PostgreSQL]     │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    DATA LAKE (C18-C21)                      │
│  ┌─────────┐    ┌─────────┐   ┌─────────┐                   │
│  │ BRONZE  │──▶│ SILVER  │──▶│  GOLD   │                   │
│  │ (raw)   │    │(process)│   │(output) │                   │
│  └─────────┘    └─────────┘   └─────────┘                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                 DATA WAREHOUSE (C13-C17)                    │
│  ┌────────────┐  ┌────────────┐  ┌────────────┐             │
│  │ fact_prices│  │ dim_symbol │  │  dim_date  │             │
│  └────────────┘  └────────────┘  └────────────┘             │
│                     DuckDB + Star Schema                    │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    EXPOSURE (C12)                           │
│                    FastAPI REST                             │
│                  Docker + Airflow                           │
└─────────────────────────────────────────────────────────────┘
```

**François :** "Tout conteneurisé ?"
**Pierre :** "Oui, `docker compose up` démarre tout."

---

## 4. Conformité à la certification (Jean)

| Bloc | Compétences | Statut |
|------|--------------|--------|
| Bloc 1 : Gestion de projet | C1-C7 | ✅100% |
| Bloc 2 : Collecte de données | C8-C12 | ✅100% |
| Bloc 3 : Entrepôt de données | C13-C17 | ✅100% |
| Bloc 4 : Lac de données | C18-C21 | ✅ 100 % |

**Toutes les 21 compétences couvertes.**

Documentation :
- 10 chapitres de rapport
- Modélisation MERISE (MCD/MLD/MPD)
- Analyse de conformité RGPD
- Documentation SCD Type 1/2

---

## 5. Feuille de route

### Terminé (MVP)
- ✅ Multi-source ingestion
- ✅ Architecture Data Lake
- ✅ Schéma en étoile DWH
- ✅ Optimisation du portefeuille
- ✅ API REST
- ✅ Orchestration des flux d'air
- ✅ Docker déploiement
- ✅ Documentation complète

### Backlog post-MVP
| Fonctionnalité | Priorité | Effort |
|---------|----------|--------|
| Authentification API | Élevé | 2 jours |
| Alertes par e-mail | Moyen | 1 jour |
| Plus d'actifs (top 20) | Moyen | 1 jour |
| Module de backtesting | Faible | 1 semaine |
| Tableau de bord Web | Faible | 2 semaines |

---

## 6. Questions et réponses

**Q (François) :** Quel est le plan de reprise après sinistre ?
**A (Pierre) :** Les volumes Docker sont persistants. La reconstruction complète à partir de zéro prend moins de 10 minutes. Les données peuvent être récupérées à partir des API.

**Q (Claire) :** Cela peut-il se connecter à notre système commercial ?
**A (Laien) :** Oui, l'API renvoie du JSON. Nous aurions besoin de créer un adaptateur pour votre système spécifique.

**Q (François) :** Quel est le coût total ?
**A (Marie) :** Zéro frais de licence - tout en open source. Uniquement les ressources de calcul (1 VM, 2 processeurs, 2 Go de RAM).

**Q (Claire) :** Quelle est la précision de l'optimisation ?
**A (Sophie) :** Un backtest sur 90 jours montre que le portefeuille optimisé surclasse de 15 à 20 % à pondération égale en fonction du risque. base.

---

## Décisions

1. ✅ **Approuvé MVP** pour le déploiement en production
2. ✅ **La phase UAT** commence le 18/02/2025 (1 semaine)
3. ✅ **Objectif de mise en ligne :** 2025-02-28
4. ✅ **Post-MVP :** L'authentification API doit être ajoutée avant l'exposition externe

---

## Éléments d'action

| Actions | Propriétaire | À payer |
|--------|-------|-----|
| Plan de test UAT | Jean | 2025-02-18 |
| Déploiement en production | Pierre | 2025-02-25 |
| Session de formation des utilisateurs | Sophie | 2025-02-27 |
| Soumission de certification | Laïen | 2025-03-10 |

---

*Procès-verbal enregistré par : Lucas Petit*
*Approuvé par : François Martin (CTO)*

