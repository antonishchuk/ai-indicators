"""SEC EDGAR XBRL companyconcept: hyperscaler capex per quarter.

10-Q cash-flow facts are year-to-date, so quarterly capex is derived by
differencing consecutive YTD facts that share a fiscal-year start date. Full
history comes back on every call; no back-fill needed.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from ..model import USD, Row
from .base import Collector

URL = "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik:010d}/us-gaap/{concept}.json"

COMPANIES = {
    "MSFT": (789019, "PaymentsToAcquirePropertyPlantAndEquipment"),
    "GOOGL": (1652044, "PaymentsToAcquirePropertyPlantAndEquipment"),
    "META": (1326801, "PaymentsToAcquirePropertyPlantAndEquipment"),
    "AMZN": (1018724, "PaymentsToAcquireProductiveAssets"),
    "ORCL": (1341439, "PaymentsToAcquirePropertyPlantAndEquipment"),
}


class Edgar(Collector):
    name = "edgar"
    raw_name = "edgar_capex.json"

    def client(self):
        c = super().client()
        # SEC requires a descriptive UA with a contact
        c.headers["User-Agent"] = "ai-indicators research dashboard aofo.uae@gmail.com"
        return c

    def fetch(self) -> bytes:
        out = {}
        with self.client() as c:
            for t, (cik, concept) in COMPANIES.items():
                r = c.get(URL.format(cik=cik, concept=concept))
                r.raise_for_status()
                out[t] = r.json()["units"]["USD"]
        return json.dumps(out).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        rows: list[Row] = []
        for t, facts in json.loads(raw).items():
            # latest filing wins for each (start, end)
            best: dict[tuple[str, str], dict] = {}
            for f in facts:
                if f.get("form") not in ("10-Q", "10-K", "10-K/A", "10-Q/A"):
                    continue
                k = (f["start"], f["end"])
                if k not in best or f["filed"] > best[k]["filed"]:
                    best[k] = f
            by_start: dict[str, list[dict]] = {}
            for (s, _e), f in best.items():
                by_start.setdefault(s, []).append(f)
            for s, fs in by_start.items():
                fs.sort(key=lambda f: f["end"])
                prev_val = 0.0
                prev_end = datetime.strptime(s, "%Y-%m-%d")
                for f in fs:
                    end = datetime.strptime(f["end"], "%Y-%m-%d")
                    days = (end - prev_end).days
                    q = f["val"] - prev_val
                    prev_val, prev_end = f["val"], end
                    if not 70 <= days <= 110:  # keep only ~one-quarter deltas
                        continue
                    rows.append(
                        Row(
                            ts=end.replace(hour=12, tzinfo=timezone.utc),
                            source=self.name,
                            entity=t,
                            metric="capex_q",
                            value=float(q),
                            unit=USD,
                            meta={"fy": f.get("fy"), "fp": f.get("fp"), "form": f.get("form"), "filed": f.get("filed")},
                        )
                    )
        return rows
