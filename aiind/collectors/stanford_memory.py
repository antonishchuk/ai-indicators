"""Stanford DAM "Memory Prices" dataset: long-run and monthly $/GB by memory type.

One CSV (https://dam.stanford.edu/memory-prices.html) that splices:

* John McCallum's historical DRAM and HDD $/GB (1957 -> 2024-07),
* monthly cheapest retail listing per GB from Keepa (Amazon) for DDR3, DDR4,
  DDR5, DRAM overall, HDD (2024-08 ->) and NAND SSD (2016-10 ->),
* a handful of analyst HBM $/GB points,
* Epoch AI's quarterly AI-accelerator component spend and cost shares (HBM,
  logic, packaging, auxiliary).

"Cheapest listing" is noisy and tracks clearance kits; it is a floor, not a
median. Cite the dataset and its underlying sources when quoting.
"""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from ..model import PCT, USD_BILLION, USD_PER_GB, Row
from .base import GENERIC_USER_AGENT, Collector, fnum

URL = "https://dam.stanford.edu/assets/memory-prices/memory-prices.csv"

# (CSV series, CSV metric) -> (entity, metric, unit)
SERIES = {
    ("DDR3 (Keepa)", "usd_per_gb"): ("ddr3", "cheapest", USD_PER_GB),
    ("DDR4 (Keepa)", "usd_per_gb"): ("ddr4", "cheapest", USD_PER_GB),
    ("DDR5 (Keepa)", "usd_per_gb"): ("ddr5", "cheapest", USD_PER_GB),
    ("DRAM cheapest (Keepa)", "usd_per_gb"): ("dram", "cheapest", USD_PER_GB),
    ("NAND cheapest (Keepa)", "usd_per_gb"): ("nand", "cheapest", USD_PER_GB),
    ("HDD cheapest (Keepa)", "usd_per_gb"): ("hdd", "cheapest", USD_PER_GB),
    ("McCallum DRAM (historical)", "usd_per_gb"): ("dram", "historical", USD_PER_GB),
    ("McCallum HDD (historical)", "usd_per_gb"): ("hdd", "historical", USD_PER_GB),
    ("NAND SSD (anchor)", "usd_per_gb"): ("nand", "historical", USD_PER_GB),
    ("HBM $/GB", "usd_per_gb"): ("hbm", "analyst", USD_PER_GB),
    ("HBM spend", "usd_billion"): ("chip_hbm", "spend", USD_BILLION),
    ("Logic spend", "usd_billion"): ("chip_logic", "spend", USD_BILLION),
    ("Packaging spend", "usd_billion"): ("chip_packaging", "spend", USD_BILLION),
    ("Auxiliary spend", "usd_billion"): ("chip_auxiliary", "spend", USD_BILLION),
    ("HBM cost share", "percent_share"): ("chip_hbm", "cost_share", PCT),
    ("Logic cost share", "percent_share"): ("chip_logic", "cost_share", PCT),
    ("Packaging cost share", "percent_share"): ("chip_packaging", "cost_share", PCT),
    ("Auxiliary cost share", "percent_share"): ("chip_auxiliary", "cost_share", PCT),
}
REQUIRED = {"date", "series", "metric", "value"}
MIN_ROWS = 500


class StanfordMemory(Collector):
    name = "stanford_memory"
    raw_name = "stanford_memory_prices.csv"
    user_agent = GENERIC_USER_AGENT

    def fetch(self) -> bytes:
        with self.client() as c:
            r = c.get(URL)
            r.raise_for_status()
            return r.content

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig")))
        if not REQUIRED <= set(reader.fieldnames or []):
            raise ValueError(f"unexpected columns: {reader.fieldnames}")
        rows: list[Row] = []
        for rec in reader:
            target = SERIES.get((rec["series"], rec["metric"]))
            v = fnum(rec["value"])
            if target is None or v is None or v < 0:
                continue
            entity, metric, unit = target
            day = datetime.strptime(rec["date"][:10], "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
            rows.append(Row(ts=day, source=self.name, entity=entity, metric=metric, value=v, unit=unit, meta={"src": rec.get("source") or ""}))
        if len(rows) < MIN_ROWS:
            raise ValueError(f"only {len(rows)} known rows; series were renamed?")
        return rows
