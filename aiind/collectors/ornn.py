"""Ornn Compute Price Index (OCPI): transaction-based $/GPU-hour.

Current value is anonymous; history requires a key, so we snapshot daily.
The index updates hourly; our daily row is the value at collection time.
"""
from __future__ import annotations

import json
from datetime import datetime

from ..model import USD_PER_GPU_HOUR, Row, now_utc
from .base import Collector

BASE = "https://api.ornnai.com/api/gpu/"

GPUS = {
    "H100 SXM": "h100_sxm",
    "H200": "h200",
    "B200": "b200",
    "A100 SXM4": "a100_sxm",
}


class Ornn(Collector):
    name = "ornn"
    raw_name = "ornn.json"

    def fetch(self) -> bytes:
        out = {}
        with self.client() as c:
            for gpu in GPUS:
                r = c.get(BASE + gpu)
                r.raise_for_status()
                out[gpu] = r.json()
        return json.dumps(out).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        ts = ts or now_utc()
        rows: list[Row] = []
        for gpu, payload in json.loads(raw).items():
            if not payload.get("success"):
                continue
            d = payload["data"]
            rows.append(
                Row(
                    ts=ts,
                    source=self.name,
                    entity=GPUS.get(gpu, gpu),
                    metric="index",
                    value=float(d["index_value"]),
                    unit=USD_PER_GPU_HOUR,
                    meta={"last_updated": d.get("last_updated"), "gpu_name": d.get("gpu_name")},
                )
            )
        return rows
