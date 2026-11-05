"""npm registry download counts, daily, last 365 days."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..model import COUNT, Row
from .base import Collector

URL = "https://api.npmjs.org/downloads/range/last-year/{pkg}"
PACKAGES = ["openai", "@anthropic-ai/sdk", "ai", "@google/genai", "@modelcontextprotocol/sdk"]


class Npm(Collector):
    name = "npm"
    raw_name = "npm.json"

    def fetch(self) -> bytes:
        out = {}
        with self.client() as c:
            for pkg in PACKAGES:
                r = c.get(URL.format(pkg=pkg))
                r.raise_for_status()
                out[pkg] = r.json()["downloads"]
        return json.dumps(out).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        rows: list[Row] = []
        for pkg, data in json.loads(raw).items():
            for rec in data:
                day = datetime.strptime(rec["day"], "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
                rows.append(Row(ts=day, source=self.name, entity=pkg, metric="downloads", value=float(rec["downloads"]), unit=COUNT))
        return rows
