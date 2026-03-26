# TODO — Dashboard Pages for Batch 2 Modules

Each task = add one page to `src/dashboard/app.py` + update nav radio + add elif routing.
Follow existing patterns: `fetch_api()`, `styled_layout(fig)`, `COLORS`, `CHART_LAYOUT`.
After ALL pages done: update CLAUDE.md demo script + README dashboard list + commit & push.

- [x] 1. Black-Litterman page — `/portfolio/black-litterman` — show equilibrium vs posterior returns bar chart, weights pie, views table
- [x] 2. HRP page — `/portfolio/hrp` — weights pie chart, comparison table vs max-Sharpe
- [x] 3. VaR Comparison page — `/portfolio/var` — grouped bar chart (3 methods x VaR/CVaR), per-asset breakdown table
- [x] 4. Shrinkage page — `/portfolio/shrinkage` — eigenvalue comparison chart (sample vs shrunk), intensity gauge, condition number
- [x] 5. Max Diversification page — `/portfolio/max-diversification` — weights pie, diversification ratio KPI, comparison with equal-weight
- [x] 6. Min Variance page — `/portfolio/min-variance` — weights pie, vol reduction KPI, comparison with equal-weight
- [x] 7. Factor Analysis page — `/portfolio/factors` — per-asset beta heatmap, R-squared bars, factor names
- [x] 8. Tail Risk page — `/portfolio/tail-risk` — portfolio metrics KPIs (skew, kurt, JB), per-asset table, normality flags
- [x] 9. Decay page — `/portfolio/decay` — tracking error line chart over time, max deviation line, rebalance threshold marker
- [x] 10. Pairs Trading page — `/portfolio/pairs` — cointegrated pairs table, top pair spread chart with z-score bands
- [ ] 11. Final sync — update CLAUDE.md (dashboard list to 30 pages), README, test count, commit & push
