"""Ramp AI Index (Ramp Economics Lab): token spend in dollars.

Two undocumented JSON endpoints that the ramp.com/data/ai-index page fetches
itself (no key, 4-hour edge cache):

* ``chart-data/tokenVolumes``: weekly ``token_spend`` (USD) and ``token_volume``
  (tokens) per model, with ``model_maker``, since 2025-01, among businesses
  using Ramp's Token Spend Management product. Weeks end on Friday
  (``period_end``), the latest week lags 1-2 weeks.
* ``chart-data/tokenPrices``: daily 7-day trailing cost and token count for
  OpenAI and Anthropic by token type, i.e. the blended price actually paid.

The raw file keeps per-model rows in a compact array form (the full payload is
5 MB of repeated field names); ``parse`` aggregates to model maker. Monthly
adoption rates (share of US businesses paying for AI, by vendor) come from the
same index via FRED in the ``fred`` collector. Attribution required: "Ramp AI
Index, ramp.com/data/ai-index". Revisions happen; git history of the raw file
keeps the snapshots.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from ..model import COUNT, USD, USD_PER_MTOK, Row, now_utc
from .base import Collector

BASE = "https://ramp.com/data/ai-index/chart-data"
URLS = {"token_volumes": f"{BASE}/tokenVolumes", "token_prices": f"{BASE}/tokenPrices"}
MIN_WEEKS = 50
VOLUME_METRICS = {"token_spend": ("token_spend_week", USD), "token_volume": ("token_volume_week", COUNT)}


def _rows(payload) -> list[dict]:
    return payload["data"] if isinstance(payload, dict) and "data" in payload else payload


def noon(day: str) -> datetime:
    return datetime.strptime(day[:10], "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)


class Ramp(Collector):
    name = "ramp"
    raw_name = "ramp_tokens.json"
    timeout = 120.0

    def fetch(self) -> bytes:
        with self.client() as c:
            r = c.get(URLS["token_volumes"])
            r.raise_for_status()
            volumes = [
                [x["period_end"], x["metric_key"], x["model_maker"], x["series_key"], x["metric_value"]]
                for x in _rows(r.json())
                if x.get("period_grain", "weekly") == "weekly"
            ]
            r = c.get(URLS["token_prices"])
            r.raise_for_status()
            prices = [
                [x["usage_date"], x["model_maker"], x["token_type"], x["token_cost_usd_7d"], x["token_count_7d"]]
                for x in _rows(r.json())
            ]
        out = {"fetched": now_utc().isoformat(), "columns": {"token_volumes": ["period_end", "metric_key", "model_maker", "series_key", "metric_value"], "token_prices": ["usage_date", "model_maker", "token_type", "token_cost_usd_7d", "token_count_7d"]}, "token_volumes": volumes, "token_prices": prices}
        return json.dumps(out, separators=(",", ":")).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        d = json.loads(raw)
        rows: list[Row] = []
        # weekly spend / volume per model maker, plus the total as entity "all"
        agg: dict[tuple[str, str, str], float] = defaultdict(float)
        for week, metric_key, maker, _model, value in d["token_volumes"]:
            if metric_key not in VOLUME_METRICS or value is None:
                continue
            agg[(week, metric_key, maker or "unknown")] += float(value)
            agg[(week, metric_key, "all")] += float(value)
        weeks = {w for w, _, _ in agg}
        if len(weeks) < MIN_WEEKS:
            raise ValueError(f"tokenVolumes covers {len(weeks)} weeks; endpoint changed?")
        for (week, metric_key, maker), value in agg.items():
            metric, unit = VOLUME_METRICS[metric_key]
            rows.append(Row(ts=noon(week), source=self.name, entity=maker, metric=metric, value=value, unit=unit))
        # blended price paid, $/1M, 7-day trailing
        for day, maker, token_type, cost, count in d["token_prices"]:
            if not count or cost is None:
                continue
            rows.append(Row(ts=noon(day), source=self.name, entity=maker, metric=f"paid_{token_type}", value=float(cost) / float(count) * 1e6, unit=USD_PER_MTOK))
        return rows
