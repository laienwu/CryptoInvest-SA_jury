# TODO — Batch 3: Strategy Comparison, Multi-Backtest, Polish

- [ ] 1. Strategy Showdown module — `src/pipeline/strategy_compare.py` + tests. Calls all 6 optimizers (Max Sharpe, HRP, Risk Parity, Min Variance, Max Diversification, Black-Litterman), returns side-by-side weights, return, vol, Sharpe. API endpoint `GET /portfolio/compare-strategies` + schema + OpenAPI. Dashboard page with comparison table + radar chart.
- [ ] 2. Multi-strategy backtest — extend `src/pipeline/backtest.py` to accept an `optimization_method` param (max_sharpe, hrp, risk_parity, min_variance, max_diversification). New endpoint `GET /portfolio/backtest/multi` returning results for all strategies. Dashboard page with overlaid equity curves.
- [ ] 3. Update soutenance slides — `docs/soutenance.html` to reflect 30 pages, 42 endpoints, 1109+ tests, 39 pipeline modules. Add slides for batch 2+3 features.
- [ ] 4. Boost test coverage — target 70%+. Run `pytest --cov` to find uncovered branches, add tests for gaps in existing modules (transform, optimize, ingest, storage, api).
- [ ] 5. Integration test — `tests/test_integration.py`. End-to-end: mock raw data → transform → optimize → backtest → verify output keys/shapes. No external deps.
- [ ] 6. Correlation regime analysis — `src/pipeline/correlation_regime.py` + tests. Compute correlations in bull vs bear periods (from regime module). Shows how diversification breaks down in crises. API endpoint `GET /portfolio/correlation-regime` + dashboard page.
- [ ] 7. Final sync — update CLAUDE.md, README (test count, features, dashboard list), OpenAPI spec, commit & push.
