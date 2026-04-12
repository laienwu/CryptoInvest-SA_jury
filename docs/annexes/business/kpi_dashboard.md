# Spécification du tableau de bord KPI

## 1. Tableau de bord de synthèse

### 1.1 KPI de performance du portefeuille

| KPI | Cible | Seuil | Source de données |
|-----|--------|-----------|-------------|
| **Rapport de Sharpe** | > 1,0 | < 0,5 = Rouge | optimiser.py |
| **Rapport annuel** | > 15% | < 5% = Rouge | optimiser.py |
| **Volatilité** | < 30 % | > 50% = Rouge | optimiser.py |
| **Réduction maximale** | < 20 % | > 30% = Rouge | calculé |
| **Erreur de suivi par rapport à la référence** | < 10 % | > 20% = Rouge | comparaison de référence |

### 1.2 Présentation du tableau de bord

```
┌─────────────────────────────────────────────────────────────────┐
│                    PORTFOLIO OPTIMIZATION DASHBOARD             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │
│  │ SHARPE RATIO │  │   RETURN     │  │  VOLATILITY  │           │
│  │    1.24      │  │   +18.5%     │  │    28.3%     │           │
│  │   ▲ +0.15    │  │   ▲ +2.1%    │  │   ▼ -1.2%    │           │
│  └──────────────┘  └──────────────┘  └──────────────┘           │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              PORTFOLIO ALLOCATION                       │    │
│  │  ┌─────┐                                                │    │
│  │  │ BTC │████████████████████████░░░░░░░  35%            │    │
│  │  │ ETH │████████████████░░░░░░░░░░░░░░░  25%            │    │
│  │  │ SOL │██████████░░░░░░░░░░░░░░░░░░░░░  15%            │    │
│  │  │ BNB │████████░░░░░░░░░░░░░░░░░░░░░░░  12%            │    │
│  │  │ ADA │██████░░░░░░░░░░░░░░░░░░░░░░░░░   8%            │    │
│  │  │OTHER│████░░░░░░░░░░░░░░░░░░░░░░░░░░░   5%            │    │
│  │  └─────┘                                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │           PERFORMANCE VS BENCHMARK (90 days)            │    │
│  │                                                         │    │
│  │  120% ┤                              ╭─── Portfolio     │    │
│  │       │                           ╭──╯                  │    │
│  │  110% ┤                      ╭────╯                     │    │
│  │       │               ╭──────╯    ╭─── BTC Benchmark    │    │
│  │  100% ┼───────────────╯──────────╯                      │    │
│  │       │                                                 │    │
│  │   90% ┤                                                 │    │
│  │       └──────────────────────────────────────────────   │    │
│  │        Jan        Feb        Mar        Apr             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 1b. KPI Frontier efficaces

| KPI | Cible | Seuil | Source de données |
|-----|--------|-----------|-------------|
| **Points frontières** | 50 | < 10 = Rouge | frontière.json |
| **Rapport de Sharpe maximum** | > 1,0 | < 0,5 = Rouge | frontière.json |
| **Vol d'écart minimum** | < Max Sharpe Vol | Violation = Rouge | frontière.json |
| **Écart de retour** | > 10% | < 5% = Rouge | frontier.json |

---

## 1c. KPI de backtest

| KPI | Cible | Seuil | Source de données |
|-----|--------|-----------|-------------|
| **Stratégie Sharpe** | > 1,0 | < 0,5 = Rouge | backtest.json |
| **Stratégie vs poids égal** | Surperformer | Sous-performance = Avertissement | backtest.json |
| **Réduction maximale** | < 20 % | > 30% = Rouge | backtest.json |
| **Rapport Calmar** | > 2.0 | < 1,0 = Rouge | backtest.json |
| **Nombre de fenêtres** | > 3 | < 3 = Avertissement | backtest.json |

---

## 2. KPI opérationnels

### 2.1 État du pipeline de données

| KPI | Cible | Mesure | Seuil d'alerte |
|-----|--------|-------------|-----------------|
| **Taux de réussite du pipeline** | 99% | Exécutions réussies / Nombre total d'exécutions | < 95 % |
| **Fraîcheur des données** | < 24h | Temps depuis la dernière mise à jour | > 48h |
| **Latence d'ingestion** | < 5 minutes | Temps de pipeline de bout en bout | > 15 minutes |
| **Exhaustivité des données** | 100% | Enregistrements non nuls / Enregistrements attendus | < 98 % |
| **Disponibilité de l'API** | 99,5% | Temps de disponibilité / Temps total | < 99 % |

### 2.2 Présentation du tableau de bord opérationnel

```
┌─────────────────────────────────────────────────────────────────┐
│                    OPERATIONS DASHBOARD                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  PIPELINE STATUS                    LAST 7 DAYS                  │
│  ┌────────────────────────┐        ┌─────────────────────────┐  │
│  │ ● Ingest      ✓ OK     │        │ Mon ████████████ 100%   │  │
│  │ ● Transform   ✓ OK     │        │ Tue ████████████ 100%   │  │
│  │ ● Optimize    ✓ OK     │        │ Wed ██████████░░  95%   │  │
│  │ ● API         ✓ OK     │        │ Thu ████████████ 100%   │  │
│  │                        │        │ Fri ████████████ 100%   │  │
│  │ Last run: 2h ago       │        │ Sat ████████████ 100%   │  │
│  │ Next run: in 22h       │        │ Sun ████████████ 100%   │  │
│  └────────────────────────┘        └─────────────────────────┘  │
│                                                                  │
│  DATA QUALITY                       SYSTEM RESOURCES             │
│  ┌────────────────────────┐        ┌─────────────────────────┐  │
│  │ Records: 2,450         │        │ CPU:    ██░░░░░░  25%   │  │
│  │ Symbols: 5             │        │ Memory: ████░░░░  45%   │  │
│  │ Date range: 90 days    │        │ Disk:   ██░░░░░░  18%   │  │
│  │ Null values: 0         │        │ Network: OK             │  │
│  │ Duplicates: 0          │        │                         │  │
│  └────────────────────────┘        └─────────────────────────┘  │
│                                                                  │
│  RECENT ALERTS                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ ⚠ 2025-01-15 08:32  Warning: API response time > 400ms   │   │
│  │ ✓ 2025-01-14 00:05  Info: Daily pipeline completed       │   │
│  │ ✓ 2025-01-13 00:04  Info: Daily pipeline completed       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. KPI de valeur commerciale

### 3.1 Mesures du retour sur investissement

| Métrique | Calcul | Cible |
|--------|-------------|--------|
| **Gain de temps** | Heures manuelles avant - Heures manuelles après | > 20h/mois |
| **Vitesse de décision** | Il est temps de générer une recommandation de portefeuille | < 5 minutes |
| **Couverture des données** | Actifs suivis / Actifs sur le marché | > 80 % parmi les 100 premiers |
| **Précision de l'analyse** | Rendement backtesté vs rendement réel | Écart < 5 % |

### 3.2 Paramètres d'adoption

| Métrique | Cible | Actuel |
|--------|--------|---------|
| Appels API par jour | > 100 | Suivi |
| Utilisateurs uniques par semaine | > 5 | Suivi |
| Rapports générés par mois | > 20 | Suivi |
| Demandes de fonctionnalités traitées | > 80% | Suivi |

---

## 4. Mise en œuvre technique

### 4.1 Sources de données pour les KPI

```python
# KPI Data Sources
KPI_SOURCES = {
    "sharpe_ratio": "data/output/weights.json",
    "annual_return": "data/output/weights.json",
    "volatility": "data/output/weights.json",
    "frontier_points": "data/output/frontier.json",
    "max_sharpe": "data/output/frontier.json",
    "strategy_sharpe": "data/output/backtest.json",
    "max_drawdown": "data/output/backtest.json",
    "calmar_ratio": "data/output/backtest.json",
    "pipeline_status": "airflow_api/dag_runs",
    "data_freshness": "data/raw/klines/*.parquet (mtime)",
    "api_uptime": "docker_healthcheck",
    "record_count": "SELECT COUNT(*) FROM fact_prices",
}
```

### 4.2 Fréquence d'actualisation

| Tableau de bord | Taux de rafraîchissement | Latence des données |
|-----------|--------------|--------------|
| Exécutif | Quotidien | T+1 jour |
| Opérationnel | En temps réel | < 1 minute |
| Valeur commerciale | Hebdomadaire | T+1 semaine |

### 4.3 Configuration des alertes

```yaml
alerts:
  - name: pipeline_failure
    condition: pipeline_success_rate < 0.95
    severity: critical
    channel: email, slack

  - name: data_stale
    condition: data_freshness > 48h
    severity: warning
    channel: slack

  - name: sharpe_low
    condition: sharpe_ratio < 0.5
    severity: info
    channel: email
```

---

## 5. Contrôle d'accès

| Rôle | Tableau de bord exécutif | Tableau de bord des opérations | Données brutes |
|------|--------------------|--------------------|----------|
| Exécutif | Voir | Voir le résumé | Non |
| Gestionnaire de portefeuille | Voir | Voir | Lire |
| Ingénieur de données | Voir | Accès complet | Accès complet |
| DevOps | Voir le résumé | Accès complet | Lire |
