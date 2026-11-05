"""Yahoo Finance chart API: daily adjusted closes for the AI equity basket.
Each run pulls two years, so history self-heals on every collection."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..model import USD, Row
from .base import Collector

URL = "https://query1.finance.yahoo.com/v8/finance/chart/{t}?range=2y&interval=1d"

TICKERS = ["NVDA", "AMD", "AVGO", "TSM", "MU", "SMCI", "VRT", "CRWV", "ORCL", "MSFT", "GOOGL", "META", "AMZN", "SMH", "SPY"]


class Yahoo(Collector):
    name = "yahoo"
    raw_name = "yahoo_chart.json"

    def client(self):
        c = super().client()
        c.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) ai-indicators/0.1"
        return c

    def fetch(self) -> bytes:
        out = {}
        with self.client() as c:
            for t in TICKERS:
                r = c.get(URL.format(t=t))
                r.raise_for_status()
                res = r.json()["chart"]["result"][0]
                ind = res["indicators"]
                closes = (ind.get("adjclose") or [{}])[0].get("adjclose") or ind["quote"][0]["close"]
                out[t] = {"timestamp": res["timestamp"], "close": closes}
        return json.dumps(out).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        rows: list[Row] = []
        for t, d in json.loads(raw).items():
            for sec, close in zip(d["timestamp"], d["close"]):
                if close is None:
                    continue
                day = datetime.fromtimestamp(sec, tz=timezone.utc).replace(hour=21, minute=0, second=0, microsecond=0)
                rows.append(Row(ts=day, source=self.name, entity=t, metric="close", value=float(close), unit=USD))
        return rows
