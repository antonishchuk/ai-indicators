"""pypistats.org: daily PyPI downloads (without mirrors), ~180 days of history."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..model import COUNT, Row
from .base import Collector

URL = "https://pypistats.org/api/packages/{pkg}/overall?mirrors=false"
PACKAGES = ["openai", "anthropic", "litellm", "google-genai", "langchain", "mcp"]


class PyPIStats(Collector):
    name = "pypistats"
    raw_name = "pypistats.json"

    def fetch(self) -> bytes:
        out = {}
        with self.client() as c:
            for pkg in PACKAGES:
                r = c.get(URL.format(pkg=pkg))
                r.raise_for_status()
                out[pkg] = r.json()["data"]
        return json.dumps(out).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        rows: list[Row] = []
        for pkg, data in json.loads(raw).items():
            for rec in data:
                if rec.get("category") not in (None, "without_mirrors"):
                    continue
                day = datetime.strptime(rec["date"], "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
                rows.append(Row(ts=day, source=self.name, entity=pkg, metric="downloads", value=float(rec["downloads"]), unit=COUNT))
        return rows
