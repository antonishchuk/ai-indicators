from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, Field, field_validator

# Units used across collectors. Keep this list short and explicit so the
# dashboard can format values without guessing.
USD_PER_GPU_HOUR = "usd_per_gpu_hour"
USD_PER_MTOK = "usd_per_mtok"  # US dollars per 1M tokens
USD = "usd"
RATIO = "ratio"
COUNT = "count"


class Row(BaseModel):
    """One observation of one series.

    A series is identified by (source, entity, metric). `date` is the
    observation date in UTC and is the dedupe key together with the series:
    collecting twice in one day keeps the later value.
    """

    ts: datetime
    source: str
    entity: str
    metric: str
    value: float
    unit: str
    meta: dict[str, Any] = Field(default_factory=dict)

    @field_validator("ts")
    @classmethod
    def _utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)

    @property
    def date(self) -> date:
        return self.ts.date()

    def to_record(self) -> dict[str, Any]:
        return {
            "date": self.date,
            "ts": self.ts.replace(tzinfo=None),
            "source": self.source,
            "entity": self.entity,
            "metric": self.metric,
            "value": float(self.value),
            "unit": self.unit,
            "meta": json.dumps(self.meta, sort_keys=True, separators=(",", ":")) if self.meta else "",
        }


def now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)
