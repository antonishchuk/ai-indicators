"""gpuperhour.com daily price index: min/p25/median/p75/max $/GPU-hour across
~30 providers, with offer and provider counts. The CSV carries history, so each
run re-imports the whole window (merge is idempotent)."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timezone

from ..model import COUNT, USD_PER_GPU_HOUR, Row
from .base import Collector, fnum

URL = "https://api.gpuperhour.com/api/price-index/export.csv?days=365"

GPUS = {
    "h100-sxm-80gb": "h100_sxm",
    "h100-pcie-80gb": "h100_pcie",
    "h100-nvl": "h100_nvl",
    "h200-sxm": "h200",
    "h200-nvl": "h200_nvl",
    "b200-sxm": "b200",
    "b300-sxm": "b300",
    "gh200": "gh200",
    "a100-sxm-80gb": "a100_sxm",
    "a100-pcie-80gb": "a100_pcie",
}

PRICE_COLS = {
    "min_price_per_gpu": "min",
    "p25_price_per_gpu": "p25",
    "median_price_per_gpu": "median",
    "p75_price_per_gpu": "p75",
    "max_price_per_gpu": "max",
}
COUNT_COLS = {"offer_count": "offers", "provider_count": "providers"}


class GpuPerHour(Collector):
    name = "gpuperhour"
    raw_name = "gpuperhour_index.csv"

    def fetch(self) -> bytes:
        with self.client() as c:
            r = c.get(URL)
            r.raise_for_status()
            return r.content

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        rows: list[Row] = []
        for rec in csv.DictReader(io.StringIO(raw.decode("utf-8"))):
            entity = GPUS.get(rec.get("gpu_slug", ""))
            if not entity:
                continue
            day = datetime.strptime(rec["snapshot_date"], "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)
            meta = {
                "gpu_name": rec.get("gpu_name"),
                "cheapest_provider": rec.get("cheapest_provider"),
                "basket_version": rec.get("basket_version"),
            }
            for col, metric in PRICE_COLS.items():
                v = fnum(rec.get(col))
                if v is None or v <= 0:
                    continue
                rows.append(Row(ts=day, source=self.name, entity=entity, metric=metric, value=v, unit=USD_PER_GPU_HOUR, meta=meta))
            for col, metric in COUNT_COLS.items():
                v = fnum(rec.get(col))
                if v is None:
                    continue
                rows.append(Row(ts=day, source=self.name, entity=entity, metric=metric, value=v, unit=COUNT, meta=meta))
        return rows
