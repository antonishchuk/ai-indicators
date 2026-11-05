# ai-indicators

Daily collector and dashboard of AI-cycle leading indicators: GPU rental
prices, LLM token prices, TSMC revenue, hyperscaler capex, credit spreads and
developer adoption. Data lives in this repo as parquet; GitHub Actions runs the
collectors once a day, commits the data and redeploys the static dashboard to
GitHub Pages.

Dashboard: https://antonishchuk.github.io/ai-indicators/
Plan and source inventory: [docs/PLAN.md](docs/PLAN.md).

## Layout

```
aiind/collectors/   one module per source: fetch() -> raw bytes, parse(raw, ts) -> rows
aiind/basket.py     curated model tiers per vendor (chains of LiteLLM keys) + OpenRouter basket
aiind/store.py      data/raw/<source> (overwritten; history in git) and data/series.parquet
aiind/run.py        CLI runner; writes data/run_status.json
aiind/build_site.py derives everything the page shows -> site/data/dashboard.json
scripts/            back-fill scripts (LiteLLM git history)
site/               static dashboard (Plotly.js), Russian UI with an explanation per indicator
data/series.parquet long table: date, ts, source, entity, metric, value, unit, meta
tests/              parse tests against the committed raw snapshots
```

A series is `(source, entity, metric)`. Units are explicit per row
(`usd_per_gpu_hour`, `usd_per_mtok`, `usd`, `pct`, `count`, ...). One row per
series per day; a second run on the same day overwrites.

## Run locally

```
python -m venv .venv
.venv/Scripts/pip install -e .[dev]           # Windows; use .venv/bin on Linux/macOS
.venv/Scripts/python -m aiind.run             # all collectors
.venv/Scripts/python -m aiind.run --only ornn,runpod
.venv/Scripts/python -m aiind.run --reparse   # re-derive series from data/raw without network
.venv/Scripts/python -m aiind.build_site      # -> site/data/dashboard.json
.venv/Scripts/python -m http.server -d site 8765   # open http://127.0.0.1:8765/
.venv/Scripts/pytest
```

Back-fill token price history from LiteLLM's git log (weekly snapshots since 2024-01):

```
python scripts/backfill_litellm.py --since 2024-01-01
```

## Query

```python
import polars as pl
df = pl.read_parquet("data/series.parquet")
df.filter(pl.col("source") == "gpuperhour").pivot("entity", index="date", values="value")
```

## Sources

| source | what | history | key |
|---|---|---|---|
| openrouter | cheapest routed $/1M for 450+ models, `created` for release cadence | daily since 2026-11-05 | none |
| openrouter_endpoints | per-provider prices for 13 open-weight models: providers, min, median, first-party | daily | none |
| litellm | first-party chat models of tracked vendors, $/1M | weekly from 2024-01 (git) | none |
| llm_prices | curated first-party list prices, $/1M | daily | none |
| ornn | OCPI transaction index $/GPU-hour: H100 SXM, H200, B200, A100 | daily | none |
| runpod | list $/GPU-hour secure/community: H100/H200/B200/B300/A100 | daily | none |
| gpuperhour | min/p25/median/p75/max $/GPU-hour across ~30 clouds, offer and provider counts | since 2026-09-14 | none |
| yahoo | adjusted closes: NVDA, AMD, AVGO, TSM, MU, SMCI, VRT, CRWV, ORCL, MSFT, GOOGL, META, AMZN, SMH, SPY | 2y | none |
| edgar | quarterly capex MSFT, GOOGL, META, AMZN, ORCL (XBRL, YTD differenced) | full | none |
| fred | HY OAS (BAMLH0A0HYM2), Henry Hub (DHHNGSP) | since 2020 | none |
| tsmc | monthly consolidated revenue, NT$ millions | since 2023 | none (site WAF is flaky) |
| pypistats | daily downloads: openai, anthropic, litellm, google-genai, langchain, mcp | 180d | none |
| npm | daily downloads: openai, @anthropic-ai/sdk, ai, @google/genai, @modelcontextprotocol/sdk | 365d | none |

Vast.ai is deliberately not used: its ToS forbids building price indices.
Artificial Analysis (intelligence index) needs a free API key and attribution; not wired yet.
