"""OpenRouter public models list: cheapest routed price per model, $/token.

No key required. Top-level pricing is the cheapest routed endpoint, not the
first-party list price; for closed vendors (openai, anthropic, google) it
matches list price in practice. First-party prices for open-weight models come
from the per-model /endpoints call (separate collector, later).
"""
from __future__ import annotations

import json

from ..model import USD_PER_MTOK, Row, now_utc
from .base import Collector, fnum

URL = "https://openrouter.ai/api/v1/models"

METRICS = {
    "prompt": "input",
    "completion": "output",
    "input_cache_read": "cache_read",
    "input_cache_write": "cache_write",
}


class OpenRouter(Collector):
    name = "openrouter"
    raw_name = "openrouter_models.json"

    def fetch(self) -> bytes:
        with self.client() as c:
            r = c.get(URL)
            r.raise_for_status()
            return r.content

    def parse(self, raw: bytes) -> list[Row]:
        ts = now_utc()
        rows: list[Row] = []
        for m in json.loads(raw)["data"]:
            pricing = m.get("pricing") or {}
            meta = {
                "name": m.get("name"),
                "created": m.get("created"),
                "context_length": m.get("context_length"),
                "canonical_slug": m.get("canonical_slug"),
            }
            for key, metric in METRICS.items():
                v = fnum(pricing.get(key))
                # router/auto models report -1 (dynamic pricing); not a price
                if v is None or v < 0:
                    continue
                rows.append(
                    Row(
                        ts=ts,
                        source=self.name,
                        entity=m["id"],
                        metric=metric,
                        value=v * 1_000_000,
                        unit=USD_PER_MTOK,
                        meta=meta,
                    )
                )
        return rows
