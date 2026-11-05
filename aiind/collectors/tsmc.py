"""TSMC monthly consolidated revenue (NT$ millions) from the IR page tables."""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone

from ..model import Row
from .base import Collector, fnum

URL = "https://investor.tsmc.com/english/monthly-revenue/{year}"
MONTHS = {m: i + 1 for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])}
FIRST_YEAR = 2023


class Tsmc(Collector):
    name = "tsmc"
    raw_name = "tsmc_monthly_revenue.json"

    def client(self):
        c = super().client()
        # the IR site WAF intermittently 403s non-browser agents; plain browser UA + retries
        c.headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
        c.headers["Accept"] = "text/html,application/xhtml+xml"
        return c

    def fetch(self) -> bytes:
        out = {}
        year_now = datetime.now(timezone.utc).year
        with self.client() as c:
            for year in range(FIRST_YEAR, year_now + 1):
                for attempt in range(4):
                    r = c.get(URL.format(year=year))
                    if r.status_code == 200:
                        out[str(year)] = self._table(r.text)
                        break
                    time.sleep(2 + 3 * attempt)
                else:
                    out[str(year)] = []  # keep going; parse() just yields nothing for this year
        if not any(out.values()):
            raise RuntimeError("TSMC: every year page failed")
        return json.dumps(out).encode()

    @staticmethod
    def _table(html: str) -> list[list[str]]:
        m = re.search(r"<table.*?</table>", html, re.S)
        if not m:
            return []
        rows = []
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(0), re.S):
            cells = [re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", c)).strip() for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if cells:
                rows.append(cells)
        return rows

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        rows: list[Row] = []
        for year, table in json.loads(raw).items():
            for cells in table:
                mon = MONTHS.get(cells[0].rstrip(".")[:3]) if cells else None
                if not mon or len(cells) < 2:
                    continue
                rev = fnum(cells[1])
                if rev is None:
                    continue
                day = datetime(int(year), mon, 1, 12, tzinfo=timezone.utc)
                meta = {"yoy": cells[2] if len(cells) > 2 else None}
                rows.append(Row(ts=day, source=self.name, entity="TSMC", metric="revenue_ntd_m", value=rev, unit="ntd_millions", meta=meta))
        return rows
