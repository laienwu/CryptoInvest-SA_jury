# Analyse du Besoin (C1)

## 1. Contexte et enjeux

### 1.1 Présentation de l'organisation
L'organisation **CryptoInvest SA** est une société de gestion d'actifs numériques souhaitant optimiser ses stratégies d'investissement en cryptomonnaies. Face à la volatilité du marché crypto, la direction souhaite mettre en place une infrastructure data permettant d'analyser les données de marché et d'optimiser l'allocation de portefeuille.

### 1.2 Expression du besoin initial
> "Nous souhaitons disposer d'un outil permettant de collecter automatiquement les données de marché crypto, de les analyser, et de proposer une allocation optimale de portefeuille basée sur la théorie moderne du portefeuille (Markowitz)."

### 1.3 Enjeux stratégiques
- **Performance** : Améliorer le rendement ajusté au risque des portefeuilles
- **Automatisation** : Réduire les tâches manuelles de collecte de données
- **Scalabilité** : Pouvoir ajouter de nouveaux actifs facilement
- **Conformité** : Respecter les réglementations (RGPD, traçabilité)

---

## 2. Grilles d'entretien

### 2.1 Entretien Direction Générale

| Question | Réponse |
|----------|---------|
| Quels sont les objectifs business du projet ? | Optimiser l'allocation de portefeuille pour maximiser le ratio rendement/risque |
| Quel est le budget alloué ? | Budget limité, privilégier les solutions open-source |
| Quels sont les délais ? | MVP en 3 mois |
| Qui sont les utilisateurs finaux ? | Équipe de gestion, analystes quantitatifs |

### 2.2 Entretien Équipe Trading

| Question | Réponse |
|----------|---------|
| Quelles données utilisez-vous actuellement ? | Prix OHLCV manuellement extraits de Binance |
| Quelle fréquence de mise à jour ? | Quotidienne suffit pour l'instant |
| Quels actifs suivez-vous ? | BTC, ETH principalement, extensible à d'autres |
| Quels indicateurs calculez-vous ? | Rendements, volatilité, corrélations |

### 2.3 Entretien IT / Infrastructure

| Question | Réponse |
|----------|---------|
| Quelle infrastructure existante ? | Serveurs Linux, pas de cloud |
| Contraintes techniques ? | Pas de base de données lourde (Postgres optionnel) |
| Compétences équipe ? | Python, SQL, Docker |
| Exigences sécurité ? | Données publiques, pas de PII |

---

## 3. Note de synthèse

### 3.1 Reformulation du besoin
Le projet vise à créer une **infrastructure data complète** pour :
1. **Collecter** automatiquement les données OHLCV depuis l'API Binance
2. **Stocker** les données dans un format optimisé (Data Lake)
3. **Transformer** les données brutes en métriques (rendements, volatilité, corrélations)
4. **Analyser** via un Data Warehouse avec requêtes SQL
5. **Optimiser** l'allocation de portefeuille (Markowitz)
6. **Exposer** les résultats via API REST

### 3.2 Périmètre fonctionnel
| Inclus | Exclus |
|--------|--------|
| Collecte API Binance | Trading automatique |
| Stockage Parquet/DuckDB | Données temps réel (streaming) |
| Calculs statistiques | Machine Learning prédictif |
| Optimisation Markowitz | Backtesting complet |
| API REST consultation | Interface graphique |

### 3.3 Moyens mobilisables
- **Humains** : 1 Data Engineer (moi)
- **Techniques** : Python, DuckDB, FastAPI, Docker
- **Financiers** : Budget limité → solutions open-source uniquement

### 3.4 Analyse RICE

| Fonctionnalité | Reach | Impact | Confidence | Effort | Score |
|----------------|-------|--------|------------|--------|-------|
| Pipeline ETL | 5 | 5 | 5 | 3 | 41.7 |
| Data Warehouse | 4 | 4 | 4 | 2 | 32.0 |
| API REST | 3 | 3 | 5 | 1 | 45.0 |
| Optimisation | 5 | 5 | 4 | 2 | 50.0 |

**Priorité** : Optimisation > API > Pipeline > DWH

### 3.5 Objectifs SMART
1. **Spécifique** : Créer un pipeline ETL collectant les données Binance
2. **Mesurable** : Traiter 2+ symboles avec données sur 90 jours
3. **Atteignable** : Technologies maîtrisées (Python, SQL)
4. **Réaliste** : Architecture simple, pas de cloud
5. **Temporel** : MVP fonctionnel en 3 mois

---

## 4. Recommandation de cadrage

### 4.1 Solution préconisée
Architecture **Data Lake + Data Warehouse** légère :
- Stockage : Parquet (lake) + DuckDB (warehouse)
- ETL : Scripts Python (ingest → transform → optimize)
- Exposition : FastAPI
- Déploiement : Docker

### 4.2 Risques identifiés
| Risque | Probabilité | Impact | Mitigation |
|--------|-------------|--------|------------|
| API Binance indisponible | Faible | Moyen | Retry + cache local |
| Volume de données | Faible | Faible | DuckDB scale bien |
| Compétences | Faible | Moyen | Documentation |

### 4.3 Prochaines étapes
1. Valider le cadrage avec le commanditaire
2. Cartographier les données disponibles
3. Définir l'architecture technique détaillée
