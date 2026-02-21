# TODO

All Phases 1–3 complete. All code review critical/medium/low items complete.
Remaining work is dashboard enhancements (Phases 4–6).

---

## Dashboard — Phase 4 — Optional enhancements

- [ ] **Risk contribution** (Dashboard page): Marginal risk contribution pie chart (weight × marginal vol). Needs helper in optimize.py + API exposure.
- [ ] **Rolling correlation** (Metrics page): Rolling 30-day correlation line chart. Client-side from `/metrics/returns`.

---

## Dashboard — Phase 5 — UX / polish

Quick wins. All computable client-side from existing API responses.

- [ ] **Cache `fetch_api`** — `@st.cache_data(ttl=300)` + "🔄 Refresh" button in sidebar. Every page switch currently re-fetches all endpoints. Makes navigation instant after first load.
- [ ] **Format backtest metrics table** — `cumulative_return = 0.15` renders as `0.15`, not `15 %`. Apply `fmt_pct()` / `fmt_ratio()` to all numeric fields in the table.
- [ ] **KPI delta vs equal weight** — `st.metric` has built-in `delta` argument. Show `Sharpe: 1.2 (+0.3 vs equal weight)`. Data already in `/portfolio/backtest`.
- [ ] **Sidebar: date range + last refresh** — pull `min(date)` / `max(date)` from klines and display `Data: 2024-11-01 → 2025-02-21`.
- [ ] **Symbols page: total return KPI** — 5th stat card `Total Return since start: +42.3 %` (last / first close − 1).
- [ ] **Chart type labels** — rename `["technical", "candlestick", "line"]` → `["Full (SMA + Bollinger + RSI)", "Candlestick + Volume", "Line only"]`.
- [ ] **Auto-refresh toggle** — `st.sidebar.toggle("Auto-refresh 30s")` + `st.rerun()`.
- [ ] **VaR x-axis label** — `render_return_distribution` formats log returns as `:.2%` (wrong). Convert to simple returns first or relabel axis as "Log Return".

---

## Dashboard — Phase 6 — New charts & Risk Analysis page

All computed client-side from existing endpoints. No new API endpoints needed.

### 6a — Dashboard page additions

- [ ] **Normalized price comparison** — all 13 symbols rebased to 1.0 on day 1, overlaid line chart. From `/klines/{sym}`. Highest jury impact single chart.
- [ ] **HHI concentration score** — 6th KPI card. `HHI = Σ(wᵢ²)`. 1/13 ≈ 0.077 = perfectly diversified, 1.0 = full concentration. From `/portfolio` weights.
- [ ] **Rolling 30-day average pairwise correlation** — single line over time showing mean correlation across all pairs. From `/metrics/returns`. Justifies the 8 new symbols added.

### 6b — New "Risk Analysis" page (6th sidebar entry, between Metrics and Frontier)

- [ ] **Rolling volatility per symbol** — 30-day rolling std × √365, overlaid line chart. Reveals vol regimes.
- [ ] **Skewness / Kurtosis table** — per-symbol: Ann. Return, Ann. Vol, Sharpe, Skewness, Kurtosis, VaR 95%. Addresses jury Q on tail risks.
- [ ] **Beta vs BTC bar chart** — regress each symbol's daily returns against BTC. β > 1 amplifies, β < 1 hedges. Horizontal sorted bar.
- [ ] **VaR / CVaR per symbol** — 95th percentile per asset, horizontal bar chart.
- [ ] **Correlation network graph** — Plotly scatter: nodes = symbols, edges = lines with opacity ∝ |ρ|, color = positive/negative. More intuitive than a heatmap for the diversification story.

### 6c — Symbols page additions

- [ ] **Compare 2 symbols** — "Compare mode" toggle; second selector; both normalized to 1.0 on shared axis.

### 6d — Backtest page additions

- [ ] **Win rate by window** — % of rolling windows where strategy beat equal weight. Bar chart + KPI.
- [ ] **Per-symbol return contribution** — stacked bar per window: (weight × return) per symbol. Shows which assets drove / dragged performance.

---

## Implementation order

```
Phase 5 (quick wins, low risk)
└── cache → format backtest table → KPI deltas → sidebar date → total return KPI → labels

Phase 6a (Dashboard additions, high jury impact)
└── normalized prices → HHI KPI → rolling avg correlation

Phase 6b (Risk page — most new code, all client-side)
└── rolling vol → skew/kurt table → beta chart → VaR per symbol → network graph

Phase 6c + 6d (smaller scope)
└── compare mode → win rate → contribution chart
```
