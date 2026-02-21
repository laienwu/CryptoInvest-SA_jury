# Questions Jury — Réponses Préparées

16 questions probables avec réponses structurées.

---

## Q1. Pourquoi PyArrow et pas Pandas ?

PyArrow est 2 à 5 fois plus efficace en mémoire que Pandas pour les opérations analytiques tabulaires, grâce au format Arrow colonnaire zero-copy. Pour un pipeline qui lit et écrit du Parquet, PyArrow le fait nativement sans sérialisation. La décision est documentée dans ADR-003 avec les alternatives considérées. Sur 13 symboles la différence est minime, mais l'architecture est prête pour 1000 symboles où la différence mémoire serait significative.

---

## Q2. Pourquoi DuckDB et pas PostgreSQL pour le DWH ?

DuckDB est OLAP embarqué sans serveur, lit directement les Parquet, et est optimisé pour les agrégations analytiques. PostgreSQL est OLTP conçu pour les transactions — excellent pour les inserts mais moins pour les scans complets de colonnes. L'ADR-002 documente ce choix : pas de besoin multi-utilisateurs, volume modéré, lecture native Parquet sans duplication. PostgreSQL est présent uniquement comme source de benchmarks (C8).

---

## Q3. Comment scale le système à 1000 symboles ?

Trois mécanismes. Le Storage ABC permet de swapper vers S3/MinIO sans toucher au pipeline. Airflow supporte le parallélisme via `expand()` ou `task_group`. DuckDB scale bien jusqu'à des dizaines de millions de lignes ; au-delà, migration vers Spark ou Trino via la même API FastAPI. La PipelineConfig centralise la liste des symboles — ajouter un symbole = un changement de config.

---

## Q4. Que se passe-t-il si l'API Binance est indisponible ?

BinanceAPISource lève une exception typée avec contexte (symbole, code HTTP). Airflow retry jusqu'à 3 fois avec backoff. Les données précédentes en Bronze restent disponibles — transformation et optimisation tournent sur j-1. Documenté dans le registre des risques (05_planification.md, section 6.1).

---

## Q5. Expliquez le modèle MERISE.

MERISE en trois niveaux. MCD : entités SYMBOL, DATE, PRICE avec cardinalités (1,n). MLD : tables relationnelles normalisées BCNF — dim_symbol, dim_date, fact_prices avec clés FK. MPD : vues DuckDB sur fichiers Parquet partitionnés. Le schéma est fonctionnel et interrogeable en SQL. Documentation complète dans 10_merise.md.

---

## Q6. Qu'est-ce qu'un SCD Type 2 et pourquoi ne pas l'avoir implémenté ?

SCD = gestion des changements lents sur les dimensions. Type 1 écrase (pas d'historique), Type 2 ajoute une ligne avec valid_from/valid_to. Les symboles crypto changent très rarement (< 0.1% de délistage sur la période). Type 1 suffit. Type 2 est documenté dans 08_scd_dimensions.md avec DDL complet et pseudo-code ETL, comme évolution future si besoin d'audit réglementaire. L'implémenter sans cas d'usage serait de l'over-engineering.

---

## Q7. Comment validez-vous les poids du portefeuille ?

Plusieurs niveaux. L'optimiseur scipy SLSQP reçoit `sum(weights) = 1` et `0 ≤ w_i ≤ max_weight`. Le fallback grid search filtre les combinaisons invalides. Le catalogue (09_catalogue_donnees.md) définit une règle de qualité : `output.weights — somme = 1.0`. Les tests test_optimize.py vérifient cette contrainte sur cas normaux et limites.

---

## Q8. Walk-forward backtest vs validation simple train/test ?

Le walk-forward divise en fenêtres glissantes : train 60j, test 30j, avance de 30j. Cela évite le data leakage et simule la gestion réelle du portefeuille dans le temps. Une coupe unique dépend du point choisi. Le walk-forward donne des métriques moyennées sur plusieurs périodes, plus représentatives. Comparaison équitable : optimisé vs equal-weight vs BTC-only sur les mêmes fenêtres.

---

## Q9. Pourquoi FastAPI et pas Flask ?

FastAPI est async natif, génère automatiquement OpenAPI 3.0 depuis les annotations Python, et supporte Depends() pour l'injection de dépendances. L'ADR-004 compare : Flask est synchrone sans DI intégrée, Django REST est surdimensionné sans besoin ORM. Le Depends() permet d'injecter MockStorage en test via dependency_override — inversion de dépendances SOLID.

---

## Q10. Comment gérez-vous la conformité RGPD ?

Les données Binance sont des cours publics — aucune PII collectée. Le RGPD ne s'applique pas directement. Par anticipation : registre des traitements préventif (3 traitements), politique de rétention (Bronze/Silver 365j, Gold 30j), procédures de suppression et d'export. Architecture privacy-by-design : minimisation, stockage local Docker, pas d'authentification utilisateur. Documentation dans 07_rgpd.md.

---

## Q11. Comment fonctionne la frontière efficiente ?

Markowitz (1952) : on minimise la variance du portefeuille (w^T Σ w) sous contraintes de budget pour différents niveaux de rendement cible. En variant la cible de min à max, on trace la frontière efficiente. Le point optimal est le max Sharpe ratio : (E[R] - Rf) / σ, avec Rf = 5%. Implémentation via scipy SLSQP. frontier.json contient 100 points, le max_sharpe, le min_variance, et la Capital Market Line.

---

## Q12. Qu'est-ce que le pattern Storage ABC ?

Interface abstraite `save()`, `load()`, `query()`. Le pipeline ne sait pas s'il parle à Parquet ou DuckDB. La factory `get_storage(backend)` retourne l'implémentation via un registry. Respecte l'OCP SOLID : ajouter S3 = implémenter la classe + l'enregistrer, zéro changement existant. En test, MockStorage injecté via dependency_override FastAPI — tests rapides et isolés du disque.

---

## Q13. À quoi sert le catalogue de données ?

C20 (09_catalogue_donnees.md) : inventaire exhaustif — pour chaque dataset : identifiant, localisation, format, schéma, source, fréquence, propriétaire, classification, règles de qualité, dépendances. Permet à un nouveau data engineer de comprendre le système sans lire le code. Data lineage complet : output.weights ← processed.covariance ← processed.returns ← raw.klines.

---

## Q14. Comment avez-vous planifié et suivi le projet ?

Approche Agile adaptée solo. 6 phases, 12 semaines, 127h estimées par Planning Poker. 5 jalons concrets avec livrables (données raw/ → métriques → DuckDB → API → soutenance). KPIs hebdomadaires : tâches complétées, jalons respectés, tests passants. 4 risques identifiés avec plans de contingence. Les 5 jalons ont été respectés, projet livré à 100%.

---

## Q15. Différence Data Lake vs Data Warehouse — pourquoi les deux ?

Le Data Lake (Bronze/Silver/Gold en Parquet) stocke toutes les données sans structure relationnelle imposée — flexible, économique. Le DWH (DuckDB, schéma en étoile) impose une structure fact+dimensions optimisée pour les requêtes SQL analytiques. Les deux coexistent car DuckDB lit directement les Parquet via des vues SQL — pas de duplication physique. C'est l'architecture lakehouse : flexibilité du lake + rigueur analytique du warehouse.

---

## Q16. Si vous pouviez refaire ce projet, que changeriez-vous ?

Trois choses. (1) SCD Type 2 dès le départ plutôt que documenté seulement — coût faible en semaine 2, gain permanent en auditabilité. (2) Streaming minimal avec WebSocket Binance pour les données intraday — démontrer la scalabilité vers le temps réel sans Kafka. (3) Tests en parallèle du code (TDD) plutôt qu'après chaque phase — éviter les cycles de refactoring. Ce qui a bien fonctionné : Storage ABC a payé immédiatement lors des tests API ; la décision PyArrow-no-pandas a forcé un typage rigoureux qui a capturé des bugs de coercition.
