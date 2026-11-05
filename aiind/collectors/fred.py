"""FRED series via the keyless fredgraph CSV export."""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone

from ..model import Row
from .base import Collector, fnum

URL = "https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}"

SERIES = {
    "BAMLH0A0HYM2": ("hy_oas", "pct"),  # ICE BofA US High Yield OAS
    "DHHNGSP": ("henry_hub", "usd_per_mmbtu"),
}


class Fred(Collector):
    name = "fred"
    raw_name = "fred.json"

    def fetch(self) -> bytes:
        out = {}
        with self.client() as c:
            for sid in SERIES:
                r = c.get(URL.format(sid=sid))
                r.raise_for_status()
                out[sid] = r.text
        return json.dumps(out).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        rows: list[Row] = []
        for sid, text in json.loads(raw).items():
            metric, unit = SERIES[sid]
            for rec in csv.DictReader(io.StringIO(text)):
                v = fnum(rec.get(sid))
                if v is None:
                    continue
                day = datetime.strptime(rec["observation_date"], "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
                if day.year < 2020:
                    continue
                rows.append(Row(ts=day, source=self.name, entity=sid, metric=metric, value=v, unit=unit))
        return rows
