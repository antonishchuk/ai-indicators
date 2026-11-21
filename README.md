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
scripts/            back-fill scripts (LiteLLM git history, OpenRouter 30-day usage, Bank of Korea indexes)
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

Back-fill the Bank of Korea export price indexes (ten months per call, the demo key's limit):

```
python scripts/backfill_ecos.py --since 2000-01
```

Back-fill 30 days of per-model OpenRouter usage (one request per model variant, ~750, throttled):

```
python scripts/backfill_openrouter_activity.py
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
| openrouter_usage | tokens and requests per model per day (all ~650 active models), weekly tokens per author (top-9 + others) and open-weight vs closed | daily since 2026-10-06 (back-fill); weekly from 2025-11 | none; undocumented `api/frontend/v1` |
| ramp | Ramp AI Index token spend: weekly $ and tokens per model maker (Token Spend Management sample), daily blended $/1M actually paid for OpenAI and Anthropic | weekly from 2025-01, daily from 2025-01 | none; undocumented `chart-data` endpoints |
| fred (Ramp) | share of US businesses paying for AI: all, OpenAI, Anthropic, xAI (RAMPAI*) | monthly since 2023-01 | none |
| ecos | Bank of Korea export price indexes, USD basis, 2020=100: DRAM, flash memory, computer storage units, system semiconductors | monthly since 2000 (back-fill) | public demo key `sample`, or `ECOS_API_KEY` |
| componentprices | retail median $/GB for DDR5, DDR4, DDR3 and $/TB for SSD, HDD (Newegg catalogue) | daily since 2026-08-03 | none |
| stanford_memory | Stanford DAM Memory Prices: monthly cheapest $/GB for DDR3/4/5, NAND SSD, HDD (Keepa/Amazon), McCallum history since 1957, Epoch AI accelerator component spend | monthly since 2024-08 (NAND 2016), quarterly spend since 2024 | none |
| diskprices | median $/GB of new RAM by form factor (SO-DIMM, UDIMM, server RDIMM; DDR4, DDR5) and $/TB of HDD, SATA, NVMe, U.2 SSD (Amazon listings) | daily since 2026-11-21, no history at the source | none |
| siliconanalysts | HBM $/GB by generation, press and analyst estimates with low / mid / high | sparse points since 2017 | none (anonymous tier, ~20 requests a day) |
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

Memory prices: TrendForce / DRAMeXchange spot tables and China Flash Market
quotes are deliberately not collected. Their public pages parse fine, but
their terms forbid republishing the data (TrendForce also names web crawlers),
the same reason Vast.ai is out. The memory section therefore rests on official
statistics (Bank of Korea), retail aggregators without such terms, and typed
analyst estimates for HBM, which has no market price at all. Silicon Analysts
allows citing with attribution; a product built substantially on their data
would need their commercial licence. The Bank of Japan's MOS-memory indexes
were skipped because its API notice asks services to register by email.

New collectors send the bare client name `ai-indicators/0.1` as User-Agent;
only SEC EDGAR needs a contact address.

OpenRouter usage comes from the undocumented endpoints behind
openrouter.ai/rankings. OpenRouter's terms forbid automated copying of site
data in general wording; the collector therefore pulls aggregate public
statistics only, three requests a day, and identifies itself in the
User-Agent. Ramp data is free to use with attribution ("Ramp AI Index,
ramp.com/data/ai-index"); the token series are the same ones behind the
Citrini Research "rolling 4-week token spend growth" chart and reproduce it.
Artificial Analysis (intelligence index) needs a free API key and attribution; not wired yet.
