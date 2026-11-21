"""diskprices.com: Amazon listings by product type, reduced to a median per type.

The page is one static table of a few thousand Amazon listings with price per
TB, refreshed every four hours. It is the only free source that separates
server memory (DDR4/DDR5 RDIMM) and enterprise SSD (U.2) from desktop parts.
There is no history: the collector stores today's medians for new items and
the series accumulates from the first run (2026-11-21).

The site has no terms page or robots.txt; its FAQ itself suggests importing
the table with a spreadsheet formula. It answers 403 to some User-Agent
strings (curl, python-requests, longer descriptive ones), so the bare client
name is sent. The raw file keeps only type, condition, $/TB and capacity for
the tracked types, not the listings themselves.
"""
from __future__ import annotations

import json
import re
import statistics
from collections import defaultdict
from datetime import datetime, timezone

from ..model import COUNT, USD_PER_GB, USD_PER_TB, Row, now_utc
from .base import GENERIC_USER_AGENT, Collector, fnum

URL = "https://diskprices.com/"
ROW = re.compile(r'<tr class="disk" data-product-type="([^"]+)" data-condition="([^"]+)" data-capacity="([^"]*)"[^>]*>(.*?)</tr>', re.S)
PER_TB = re.compile(r'<td class="price-per-tb">\s*\$([0-9.,]+)\s*</td>')
UPDATED = re.compile(r"Last updated at (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d) UTC")

# product type on the page -> (entity, unit). RAM is priced per GB, storage per TB.
TYPES = {
    "ddr5u": ("ddr5_udimm", USD_PER_GB),
    "ddr5so": ("ddr5_sodimm", USD_PER_GB),
    "ddr5r": ("ddr5_rdimm", USD_PER_GB),
    "ddr4u": ("ddr4_udimm", USD_PER_GB),
    "ddr4so": ("ddr4_sodimm", USD_PER_GB),
    "ddr4r": ("ddr4_rdimm", USD_PER_GB),
    "internal_hdd": ("hdd", USD_PER_TB),
    "internal_ssd": ("sata_ssd", USD_PER_TB),
    "m2_nvme": ("nvme_ssd", USD_PER_TB),
    "u2": ("u2_ssd", USD_PER_TB),
}
MIN_LISTINGS = 5   # fewer new listings than this and a median is not meaningful
MIN_ROWS = 300     # the page has ~1500 rows of tracked types; far fewer means the markup changed


class DiskPrices(Collector):
    name = "diskprices"
    raw_name = "diskprices.json"
    user_agent = GENERIC_USER_AGENT
    timeout = 120.0

    def fetch(self) -> bytes:
        with self.client() as c:
            r = c.get(URL)
            r.raise_for_status()
            html = r.text
        rows = []
        for ptype, cond, cap, body in ROW.findall(html):
            if ptype not in TYPES:
                continue
            m = PER_TB.search(body)
            per_tb = fnum(m.group(1)) if m else None
            if per_tb is not None:
                rows.append([ptype, cond, per_tb, fnum(cap)])
        if len(rows) < MIN_ROWS:
            raise ValueError(f"only {len(rows)} listings parsed; markup changed?")
        upd = UPDATED.search(html)
        out = {"fetched": now_utc().isoformat(), "updated": upd.group(1) if upd else None, "columns": ["type", "condition", "usd_per_tb", "capacity_gb"], "rows": rows}
        return json.dumps(out, separators=(",", ":")).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        d = json.loads(raw)
        if d.get("updated"):
            when = datetime.strptime(d["updated"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        else:
            when = ts or datetime.fromisoformat(d["fetched"])
        by_type: dict[str, list[float]] = defaultdict(list)
        for ptype, cond, per_tb, _cap in d["rows"]:
            if cond == "new" and ptype in TYPES and per_tb and per_tb > 0:
                by_type[ptype].append(per_tb)
        rows: list[Row] = []
        for ptype, vals in by_type.items():
            if len(vals) < MIN_LISTINGS:
                continue
            entity, unit = TYPES[ptype]
            med = statistics.median(vals)
            value = med / 1000 if unit == USD_PER_GB else med
            rows.append(Row(ts=when, source=self.name, entity=entity, metric="median", value=value, unit=unit))
            rows.append(Row(ts=when, source=self.name, entity=entity, metric="listings", value=float(len(vals)), unit=COUNT))
        if not rows:
            raise ValueError("no product type had enough new listings")
        return rows
