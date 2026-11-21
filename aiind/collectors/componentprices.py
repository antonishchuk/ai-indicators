"""ComponentPrices: daily retail medians for RAM by generation, SSD and HDD.

componentprices.com publishes, per category, the median price per GB (RAM) or
per TB (SSD, HDD) over the products it observed that day on Newegg, with the
product count. Each page carries the full daily table since 2026-08-03 as
static HTML, so one fetch per category refreshes the whole history. robots.txt
allows everything and the terms have no automated-access clause.

The raw file keeps only the first <table> of each page.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone

from ..model import COUNT, USD_PER_GB, USD_PER_TB, Row
from .base import GENERIC_USER_AGENT, Collector, fnum

BASE = "https://componentprices.com/"
# entity -> (page path, unit, the unit letters the table header must show)
PAGES = {
    "ddr5": ("ram/price-chart/ddr5", USD_PER_GB, "GB"),
    "ddr4": ("ram/price-chart/ddr4", USD_PER_GB, "GB"),
    "ddr3": ("ram/price-chart/ddr3", USD_PER_GB, "GB"),
    "ram": ("ram/price-chart", USD_PER_GB, "GB"),
    "ssd": ("ssd/price-chart", USD_PER_TB, "TB"),
    "hdd": ("hard-drives/price-chart", USD_PER_TB, "TB"),
}
TABLE = re.compile(r"<table.*?</table>", re.S)
HEADER_UNIT = re.compile(r'<th scope="col">USD / (GB|TB)</th>')
ROW = re.compile(r'<tr>\s*<th scope="row">([^<]+)</th>\s*<td>([^<]*)</td>\s*<td>([^<]*)</td>', re.S)
MIN_DAYS = 30  # the table has had 80+ priced days since launch; far fewer means the markup changed


def parse_day(s: str) -> datetime:
    s = s.strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s, fmt).replace(hour=12, tzinfo=timezone.utc)
        except ValueError:
            continue
    raise ValueError(f"unrecognised date {s!r}")


class ComponentPrices(Collector):
    name = "componentprices"
    raw_name = "componentprices.json"
    user_agent = GENERIC_USER_AGENT

    def fetch(self) -> bytes:
        out = {}
        with self.client() as c:
            for entity, (path, _unit, _letters) in PAGES.items():
                r = c.get(BASE + path)
                r.raise_for_status()
                m = TABLE.search(r.text)
                if not m:
                    raise ValueError(f"{path}: no <table> in the page")
                out[entity] = m.group(0)
        return json.dumps(out).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        rows: list[Row] = []
        for entity, table in json.loads(raw).items():
            _path, unit, letters = PAGES[entity]
            head = HEADER_UNIT.search(table)
            if not head or head.group(1) != letters:
                raise ValueError(f"{entity}: expected a 'USD / {letters}' column, got {head.group(0) if head else 'none'}")
            priced = 0
            for day_s, price_s, n_s in ROW.findall(table):
                price = fnum(price_s.replace("$", "")) if price_s.strip().startswith("$") else None
                if price is None:  # "No observation" days
                    continue
                day = parse_day(day_s)
                rows.append(Row(ts=day, source=self.name, entity=entity, metric="median", value=price, unit=unit))
                n = fnum(n_s)
                if n is not None:
                    rows.append(Row(ts=day, source=self.name, entity=entity, metric="products", value=n, unit=COUNT))
                priced += 1
            if priced < MIN_DAYS:
                raise ValueError(f"{entity}: only {priced} priced days parsed; markup changed?")
        return rows
