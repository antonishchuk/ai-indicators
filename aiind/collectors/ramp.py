"""Ramp AI Index (Ramp Economics Lab): token spend and volume by model maker.

Two undocumented JSON endpoints that the ramp.com/data/ai-index page fetches
itself (no key, 4-hour edge cache):

* ``chart-data/tokenVolumes``: weekly ``token_spend`` and ``token_volume`` per
  model, with ``model_maker``, since 2025-01, among businesses using Ramp's AI
  Token Spend Management product. The latest week lags 1-2 weeks.
* ``chart-data/tokenPrices``: daily blended price actually paid per 1M tokens
  for OpenAI, Anthropic and the blend, by token type.

The format has changed once already, so both shapes are read:

* until 2026-11: spend in absolute USD, Saturday-Friday weeks; prices as a
  7-day cost and token count per ``model_maker``.
* since 2026-11: spend and volume as an INDEX in undocumented units (the dollar
  level is no longer published), Monday-Sunday weeks, history revised (the two
  vintages differ by a non-constant factor, so they must not be spliced);
  prices as ``price_per_million`` per ``series_key``.

Series written:

* ``token_spend_index`` / ``token_volume_index`` per model maker and ``all``,
  weekly, unit ``index``. Growth rates and shares are meaningful; the level is
  not. The pre-change dollar rows (``token_spend_week``, ``token_volume_week``,
  through 2026-10-23) stay in the store as a frozen vintage and are not updated.
* ``paid_<token_type>`` per maker, daily, $/1M.

The raw file keeps per-model rows in a compact array form (the full payload is
6 MB of repeated field names). Monthly adoption rates come from the same index
via FRED in the ``fred`` collector. Attribution required: "Ramp AI Index,
ramp.com/data/ai-index". Ramp revises history whenever a business connects a
new provider; git history of the raw file keeps the snapshots.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone

from ..model import USD_PER_MTOK, Row, now_utc
from .base import Collector

BASE = "https://ramp.com/data/ai-index/chart-data"
URLS = {"token_volumes": f"{BASE}/tokenVolumes", "token_prices": f"{BASE}/tokenPrices"}
MIN_WEEKS = 50
INDEX = "index"
VOLUME_METRICS = {"token_spend": "token_spend_index", "token_volume": "token_volume_index"}
# The index totals a few hundred per week. Six figures means Ramp went back to absolute
# dollars (or changed units again) and the series needs relabelling, not silent mixing.
MAX_INDEX_TOTAL = 1e5


def _rows(payload) -> list[dict]:
    return payload["data"] if isinstance(payload, dict) and "data" in payload else payload


def _price(x: dict) -> float | None:
    """$/1M tokens from either shape of a tokenPrices record."""
    if x.get("price_per_million") is not None:
        return float(x["price_per_million"])
    cost, count = x.get("token_cost_usd_7d"), x.get("token_count_7d")
    if cost is None or not count:
        return None
    return float(cost) / float(count) * 1e6


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
                [x["period_end"], x["metric_key"], x.get("model_maker") or "unknown", x.get("series_key"), x["metric_value"]]
                for x in _rows(r.json())
                if x.get("period_grain", "weekly") == "weekly"
            ]
            r = c.get(URLS["token_prices"])
            r.raise_for_status()
            prices = [
                [x["usage_date"], x.get("series_key") or x.get("model_maker"), x["token_type"], _price(x)]
                for x in _rows(r.json())
            ]
        out = {
            "fetched": now_utc().isoformat(),
            "columns": {
                "token_volumes": ["period_end", "metric_key", "model_maker", "series_key", "metric_value"],
                "token_prices": ["usage_date", "maker", "token_type", "price_per_million"],
            },
            "token_volumes": volumes,
            "token_prices": prices,
        }
        return json.dumps(out, separators=(",", ":")).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        d = json.loads(raw)
        rows: list[Row] = []
        # weekly spend / volume index per model maker, plus the total as entity "all"
        agg: dict[tuple[str, str, str], float] = defaultdict(float)
        for week, metric_key, maker, _model, value in d["token_volumes"]:
            if metric_key not in VOLUME_METRICS or value is None:
                continue
            agg[(week, metric_key, maker or "unknown")] += float(value)
            agg[(week, metric_key, "all")] += float(value)
        weeks = sorted({w for w, _, _ in agg})
        if len(weeks) < MIN_WEEKS:
            raise ValueError(f"tokenVolumes covers {len(weeks)} weeks; endpoint changed?")
        latest_total = agg.get((weeks[-1], "token_spend", "all"), 0.0)
        if latest_total > MAX_INDEX_TOTAL:
            raise ValueError(f"token_spend total {latest_total:.0f} is not index-sized; Ramp changed units again?")
        for (week, metric_key, maker), value in agg.items():
            rows.append(Row(ts=noon(week), source=self.name, entity=maker, metric=VOLUME_METRICS[metric_key], value=value, unit=INDEX))
        # blended price actually paid, $/1M
        for day, maker, token_type, price in d["token_prices"]:
            if price is None or not maker:
                continue
            rows.append(Row(ts=noon(day), source=self.name, entity=maker, metric=f"paid_{token_type}", value=float(price), unit=USD_PER_MTOK))
        return rows
