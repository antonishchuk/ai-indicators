"""Bank of Korea ECOS: export price indexes for memory, monthly, 2020=100, USD basis.

Korea ships most of the world's DRAM and a large share of NAND, so the Bank of
Korea's export price index is the closest thing to an official contract-price
series split by memory type. Table 402Y016 (Export Price Indices, Item Groups)
has DRAM since 1971 and flash memory since 2000; system semiconductors are
kept as the non-memory comparator and computer storage units as an SSD proxy.
The month is published around the middle of the following month.

Auth: ECOS serves real data to the public demo key ``sample`` but caps each
call at 10 rows, which is exactly one series for ten months. Set ECOS_API_KEY
(free registration at ecos.bok.or.kr) to stop depending on the demo key.
History comes from scripts/backfill_ecos.py.
"""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone

import httpx

from ..model import Row, now_utc
from .base import GENERIC_USER_AGENT, Collector, fnum

URL = "https://ecos.bok.or.kr/api/StatisticSearch/{key}/json/en/1/{rows}/{stat}/M/{start}/{end}/{item}/{basis}"
BASIS = "D"  # dollar basis; C = contract currency, W = won
WINDOW = 10  # months per call: the demo key returns at most 10 rows
UNIT = "index_2020"
METRIC = "export_price_usd"

# entity -> (statistic table, item code)
SERIES = {
    "dram": ("402Y016", "30911201AA"),
    "flash": ("402Y016", "30911202AA"),
    "system_semi": ("402Y016", "30911203AA"),
    "storage_units": ("402Y016", "30941201AA"),
}


def api_key() -> str:
    return os.environ.get("ECOS_API_KEY") or "sample"


def shift_month(d: date, months: int) -> date:
    y, m = divmod(d.year * 12 + d.month - 1 + months, 12)
    return date(y, m + 1, 1)


def fetch_window(c: httpx.Client, entity: str, start: date, end: date) -> list[dict]:
    """Rows of one series for start..end (inclusive, at most WINDOW months). No data yet -> []."""
    stat, item = SERIES[entity]
    url = URL.format(key=api_key(), rows=WINDOW, stat=stat, start=start.strftime("%Y%m"), end=end.strftime("%Y%m"), item=item, basis=BASIS)
    r = c.get(url)
    r.raise_for_status()
    d = r.json()
    if "StatisticSearch" in d:
        return d["StatisticSearch"]["row"]
    result = d.get("RESULT", {})
    if result.get("CODE") == "INFO-200":  # "no data" for the window
        return []
    raise ValueError(f"ECOS {entity}: {result.get('CODE')} {result.get('MESSAGE')}")


def to_rows(source: str, entity: str, recs: list[dict]) -> list[Row]:
    rows: list[Row] = []
    for rec in recs:
        v = fnum(rec.get("DATA_VALUE"))
        t = rec.get("TIME") or ""
        if v is None or len(t) != 6:
            continue
        day = datetime(int(t[:4]), int(t[4:]), 1, 12, tzinfo=timezone.utc)
        rows.append(Row(ts=day, source=source, entity=entity, metric=METRIC, value=v, unit=UNIT))
    return rows


class Ecos(Collector):
    name = "ecos"
    raw_name = "ecos.json"
    user_agent = GENERIC_USER_AGENT

    def fetch(self) -> bytes:
        end = now_utc().date().replace(day=1)
        start = shift_month(end, -(WINDOW - 1))
        out: dict = {"fetched": now_utc().isoformat(), "series": {}}
        with self.client() as c:
            for entity in SERIES:
                out["series"][entity] = fetch_window(c, entity, start, end)
        return json.dumps(out, separators=(",", ":")).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        rows: list[Row] = []
        for entity, recs in json.loads(raw)["series"].items():
            got = to_rows(self.name, entity, recs)
            if not got:
                raise ValueError(f"ECOS returned no rows for {entity}")
            rows += got
        return rows
