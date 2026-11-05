"""OpenRouter per-model endpoints: every provider hosting an open-weight model
with its own price. Gives the first-party list price (when the vendor hosts on
OpenRouter), the cheapest and median third-party price, and how many providers
serve the model: a live read on the open-weight inference market."""
from __future__ import annotations

import json
import statistics
from datetime import datetime

from ..basket import OPENROUTER_OPEN_WEIGHT, OPENROUTER_FIRST_PARTY
from ..model import COUNT, USD_PER_MTOK, Row, now_utc
from .base import Collector, fnum

BASE = "https://openrouter.ai/api/v1/models/"


class OpenRouterEndpoints(Collector):
    name = "openrouter_endpoints"
    raw_name = "openrouter_endpoints.json"

    def fetch(self) -> bytes:
        out = {}
        with self.client() as c:
            for model_id in OPENROUTER_OPEN_WEIGHT:
                r = c.get(f"{BASE}{model_id}/endpoints")
                if r.status_code == 404:
                    out[model_id] = None
                    continue
                r.raise_for_status()
                out[model_id] = r.json().get("data")
        return json.dumps(out).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        ts = ts or now_utc()
        rows: list[Row] = []
        for model_id, data in json.loads(raw).items():
            if not data:
                continue
            eps = [e for e in data.get("endpoints", []) if e.get("pricing")]
            outs = [fnum(e["pricing"].get("completion")) for e in eps]
            ins = [fnum(e["pricing"].get("prompt")) for e in eps]
            outs = [v * 1e6 for v in outs if v is not None and v > 0]
            ins = [v * 1e6 for v in ins if v is not None and v > 0]
            if not outs:
                continue
            meta = {"name": data.get("name")}
            rows.append(Row(ts=ts, source=self.name, entity=model_id, metric="providers", value=len(outs), unit=COUNT, meta=meta))
            rows.append(Row(ts=ts, source=self.name, entity=model_id, metric="min_output", value=min(outs), unit=USD_PER_MTOK, meta=meta))
            rows.append(Row(ts=ts, source=self.name, entity=model_id, metric="median_output", value=statistics.median(outs), unit=USD_PER_MTOK, meta=meta))
            if ins:
                rows.append(Row(ts=ts, source=self.name, entity=model_id, metric="median_input", value=statistics.median(ins), unit=USD_PER_MTOK, meta=meta))
            fp_names = OPENROUTER_FIRST_PARTY.get(model_id.split("/")[0], ())
            fp = [e for e in eps if e.get("provider_name") in fp_names]
            if fp:
                o = fnum(fp[0]["pricing"].get("completion"))
                i = fnum(fp[0]["pricing"].get("prompt"))
                if o:
                    rows.append(Row(ts=ts, source=self.name, entity=model_id, metric="fp_output", value=o * 1e6, unit=USD_PER_MTOK, meta=meta | {"provider": fp[0]["provider_name"]}))
                if i:
                    rows.append(Row(ts=ts, source=self.name, entity=model_id, metric="fp_input", value=i * 1e6, unit=USD_PER_MTOK, meta=meta | {"provider": fp[0]["provider_name"]}))
        return rows
