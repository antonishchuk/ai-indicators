# ai-indicators

Daily collector of AI-cycle leading indicators: GPU rental prices, LLM token
prices, and later supply-chain, capex and adoption series. Data lives in this
repo as parquet; GitHub Actions runs the collectors once a day and commits.

Plan and source inventory: [docs/PLAN.md](docs/PLAN.md).

## Layout

```
aiind/collectors/   one module per source: fetch() -> raw bytes, parse(raw) -> rows
aiind/store.py      data/raw/<source> (overwritten; history in git) and data/series.parquet
aiind/run.py        CLI runner
data/raw/           latest raw payload per source
data/series.parquet long table: date, ts, source, entity, metric, value, unit, meta
tests/              parse tests against the committed raw snapshots
```

A series is `(source, entity, metric)`. Units are explicit per row
(`usd_per_gpu_hour`, `usd_per_mtok`, ...). One row per series per day; a
second run on the same day overwrites.

## Run locally

```
python -m venv .venv
.venv/Scripts/pip install -e .[dev]      # Windows; use .venv/bin on Linux/macOS
.venv/Scripts/python -m aiind.run        # all collectors
.venv/Scripts/python -m aiind.run --only ornn,runpod
.venv/Scripts/python -m aiind.run --reparse   # re-derive series from data/raw without network
.venv/Scripts/pytest
```

## Query

```python
import polars as pl
df = pl.read_parquet("data/series.parquet")
df.filter(pl.col("source") == "ornn").pivot("entity", index="date", values="value")
```

## Sources in v0

| source | what | key |
|---|---|---|
| openrouter | cheapest routed $/1M for 450+ models | none |
| litellm | first-party chat models of tracked vendors, $/1M | none |
| llm_prices | curated first-party list prices, $/1M | none |
| ornn | OCPI transaction index $/GPU-hour: H100 SXM, H200, B200, A100 | none |
| runpod | list $/GPU-hour secure/community: H100/H200/B200/B300/A100 | none |

Attribution: Artificial Analysis and amcompute data (when added) require attribution.
Vast.ai is deliberately not used: its ToS forbids building price indices.
