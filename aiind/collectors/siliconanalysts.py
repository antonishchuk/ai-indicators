"""Silicon Analysts: HBM price per GB by generation.

There is no public market price for HBM: it sells under long-term contracts.
siliconanalysts.com curates press and analyst prints into typed, sourced
points (low / mid / high, confidence, estimate vs confirmed) and serves them
from a documented keyless API (robots.txt allows /api/v1/market-data/, limit
about 20 requests a day per IP). The anonymous tier returns the recent points
of each series; the full history needs a free key, which is not used here.

Licence: citing with attribution and a link is free; building a data product
substantially on this data needs their commercial licence. One card with the
source named is the intended use here.

``period_sort_key`` is a sort key, not a date: YYYY followed by 00 for a
calendar year, 01-04 for quarters (halves use 01 and 03), 05 for a late-year
print. It is mapped to the first day of a representative month.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..model import USD_PER_GB, Row
from .base import GENERIC_USER_AGENT, Collector, fnum

URL = "https://siliconanalysts.com/api/v1/market-data/hbm-pricing"
SUB_MONTH = {0: 1, 1: 2, 2: 5, 3: 8, 4: 11, 5: 12}
MIN_POINTS = 10


def period_date(sort_key) -> datetime:
    year, sub = divmod(int(sort_key), 100)
    return datetime(year, SUB_MONTH.get(sub, 12), 1, 12, tzinfo=timezone.utc)


class SiliconAnalysts(Collector):
    name = "siliconanalysts"
    raw_name = "siliconanalysts_hbm.json"
    user_agent = GENERIC_USER_AGENT

    def fetch(self) -> bytes:
        with self.client() as c:
            r = c.get(URL)
            r.raise_for_status()
            return r.content

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        points = json.loads(raw)["data"]["dataPoints"]
        if len(points) < MIN_POINTS:
            raise ValueError(f"only {len(points)} HBM points; API changed or rate-limited?")
        rows: list[Row] = []
        for p in points:
            low, mid, high = fnum(p.get("value_low")), fnum(p.get("value_mid")), fnum(p.get("value_high"))
            if mid is None and low is not None and high is not None:
                mid = (low + high) / 2
            if mid is None or not p.get("series_key") or p.get("period_sort_key") is None:
                continue
            day = period_date(p["period_sort_key"])
            meta = {
                "period": p.get("period_label"),
                "type": p.get("data_type"),
                "confidence": p.get("confidence"),
                "src": p.get("source_name"),
                "projection": bool(p.get("is_projection")),
            }
            for metric, v in (("usd_per_gb", mid), ("usd_per_gb_low", low), ("usd_per_gb_high", high)):
                if v is not None:
                    rows.append(Row(ts=day, source=self.name, entity=p["series_key"], metric=metric, value=v, unit=USD_PER_GB, meta=meta))
        return rows
