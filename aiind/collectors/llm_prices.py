"""llm-prices.com (Simon Willison): hand-curated first-party list prices, $/1M."""
from __future__ import annotations

import json

from ..model import USD_PER_MTOK, Row, now_utc
from .base import Collector, fnum

URL = "https://www.llm-prices.com/current-v1.json"


class LlmPrices(Collector):
    name = "llm_prices"
    raw_name = "llm_prices_current.json"

    def fetch(self) -> bytes:
        with self.client() as c:
            r = c.get(URL)
            r.raise_for_status()
            return r.content

    def parse(self, raw: bytes) -> list[Row]:
        ts = now_utc()
        doc = json.loads(raw)
        rows: list[Row] = []
        for p in doc["prices"]:
            entity = f"{p['vendor']}/{p['id']}"
            meta = {"name": p.get("name"), "updated_at": doc.get("updated_at")}
            for key, metric in (("input", "input"), ("output", "output"), ("input_cached", "cache_read")):
                v = fnum(p.get(key))
                if v is None:
                    continue
                rows.append(
                    Row(ts=ts, source=self.name, entity=entity, metric=metric, value=v, unit=USD_PER_MTOK, meta=meta)
                )
        return rows
