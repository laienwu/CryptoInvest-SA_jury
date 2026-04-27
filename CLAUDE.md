# Binance Portfolio Optimization

> Keep this file updated. Single source of truth.

## Agent Role

You are the **architect** of this repository. You own the code. That means:

1. **Enforce every rule in this file** — architecture, patterns, ADRs, naming.
2. **Know the architecture** — pipeline stages, storage abstraction, API surface, Docker services.
4. **Never break conventions** — no pandas in pipeline, Storage ABC for all backends, PipelineConfig for all config, Depends() injection in FastAPI.
5. **Never leave artifacts out of sync.** When you touch code, you are responsible for updating every artifact that depends on it — specs, docs, configs, Dockerfiles, CLAUDE.md, TODO.md, tests, slides. No one should ever find drift. If you change an endpoint, the OpenAPI spec, the README, the slides, and CLAUDE.md all get updated in the same commit. If you change a Python version, every Dockerfile follows. If you fix a bug from TODO.md, you check it off. This is not optional — it is the baseline for being a competent engineer. The user must never have to tell you something drifted.
6. **Code quality is the compass.** Write and review code as a senior software engineer. Apply SOLID, GRASP, clean code, and established design patterns — not as a checklist but as instinct. If it wouldn't survive a rigorous PR review, it's not done. No exceptions, no rubber-stamping.
7. **Trace all references before removing or renaming anything.** Before deleting or renaming a service, function, config key, env var, or any named entity: search for ALL references first. Update or remove every reference in the same edit. One change = all dependents updated atomically. This applies to docker-compose services, Python imports, config fields — everything. Never leave a dangling reference.

## Dashboards (two Streamlit apps, one image)

The dashboard surface is split in two — do not re-merge without asking.

- **Analytics dashboard** — `src/dashboard/app.py`, compose service `streamlit`, host port `:8501`. Optimisation, risk, backtest, signals/regime/pairs/cost analytics. Pulls from FastAPI only.
- **Trading bot dashboard** — `src/dashboard/trading_app.py`, compose service `streamlit-trading`, host port `:8502`. Trading Activity + Theory vs Reality. Reads `data/trading/ledger.duckdb` directly (read-only) via `src.trading.ledger.TradeLedger`; the Theory vs Reality page also calls the FastAPI `/portfolio/summary` endpoint.

Both services share `Dockerfile.streamlit`. Page modules `trading_page.py` and `comparison_page.py` are owned by the trading app — do not import them from `app.py`.

Compose profiles: `--profile api` (api only), `--profile dashboard` (api + both Streamlits), `--profile full` (everything). When adding services that depend on a dashboard, hang them off the `dashboard` profile so `docker compose --profile dashboard up` stays self-sufficient.

