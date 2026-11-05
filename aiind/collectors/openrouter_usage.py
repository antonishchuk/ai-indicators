"""OpenRouter usage: tokens and requests per model per day, plus weekly vendor
market share and the open-weight / closed split with a year of history.

These are the undocumented JSON endpoints behind openrouter.ai/rankings
(``/api/frontend/v1/...``). No key, public Cloudflare cache, three requests a
day. The path prefix changed once already (unversioned -> v1), so ``parse``
refuses payloads that look truncated instead of silently writing nothing.

Note on terms: OpenRouter's terms of service forbid automated copying of site
information in general wording. This collector pulls aggregate public
statistics only, identifies itself in the User-Agent, and stays at a few
hundred KB a day.

Series written (unit ``count``):

* per model variant and day (entity ``author/model-permaslug[:batch|:free]``):
  ``prompt_tokens``, ``completion_tokens``, ``cached_tokens``, ``requests``.
  ``view=day`` is yesterday UTC, the only complete day; rows are keyed by the
  row's own date, not the fetch time.
* per author and ISO week (entity = author slug, ``others`` for the rest):
  ``tokens_week``. Top-9 authors of each week plus ``others``; an author that
  drops out of the top 9 has no row that week.
* ``open_weight`` / ``closed`` per week: ``tokens_week``.

The current partial week and partial day are never stored.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from ..model import COUNT, Row, now_utc
from .base import Collector

BASE = "https://openrouter.ai/api/frontend/v1"
URLS = {
    "day": f"{BASE}/rankings/models?view=day",
    "authors": f"{BASE}/rankings/author-market-share",
    "open_closed": f"{BASE}/rankings/open-closed",
}

# dashboard metric -> field in a rankings/models or stats/model-activity record
DAY_METRICS = {
    "prompt_tokens": "total_prompt_tokens",
    "completion_tokens": "total_completion_tokens",
    "cached_tokens": "total_native_tokens_cached",
    "requests": "count",
}
MIN_DAY_ROWS = 100  # 600+ normally; far fewer means the endpoint changed or broke
MIN_WEEKS = 10
AUTHOR_RENAME = {"Others": "others"}
OPEN_CLOSED_RENAME = {"open": "open_weight", "closed": "closed"}


def usage_entity(permaslug: str, variant: str | None) -> str:
    """'openai/gpt-4o-mini' + 'batch' -> 'openai/gpt-4o-mini:batch'; standard has no suffix."""
    return permaslug if variant in (None, "", "standard") else f"{permaslug}:{variant}"


def split_entity(entity: str) -> tuple[str, str]:
    """Inverse of usage_entity: -> (permaslug, variant)."""
    if ":" in entity:
        slug, variant = entity.rsplit(":", 1)
        return slug, variant
    return entity, "standard"


def noon(day: str) -> datetime:
    return datetime.strptime(day[:10], "%Y-%m-%d").replace(hour=12, tzinfo=timezone.utc)


def day_rows(source: str, recs: list[dict]) -> list[Row]:
    """Rows from rankings/models (view=day) or stats/model-activity records (same schema)."""
    rows: list[Row] = []
    for r in recs:
        if not r.get("model_permaslug"):  # the ranking carries one anonymous zero row
            continue
        entity = usage_entity(r["model_permaslug"], r.get("variant"))
        ts = noon(r["date"])
        for metric, key in DAY_METRICS.items():
            v = r.get(key)
            if v is None:
                continue
            rows.append(Row(ts=ts, source=source, entity=entity, metric=metric, value=float(v), unit=COUNT))
    return rows


def weekly_rows(source: str, points: list[dict], today: date, rename: dict[str, str]) -> list[Row]:
    """{'x': monday, 'ys': {key: tokens}} points -> one row per key; the current week is dropped."""
    rows: list[Row] = []
    for p in points:
        monday = date.fromisoformat(p["x"][:10])
        if monday + timedelta(days=7) > today:
            continue
        for key, v in p["ys"].items():
            if v is None:
                continue
            rows.append(Row(ts=noon(p["x"]), source=source, entity=rename.get(key, key), metric="tokens_week", value=float(v), unit=COUNT))
    return rows


def _points(block) -> list[dict]:
    # author-market-share wraps the points as {"data": [...], "cachedAt": ...}; open-closed is a bare list
    return block["data"] if isinstance(block, dict) else block


class OpenRouterUsage(Collector):
    name = "openrouter_usage"
    raw_name = "openrouter_usage.json"

    def fetch(self) -> bytes:
        out: dict = {"fetched": now_utc().isoformat()}
        with self.client() as c:
            for key, url in URLS.items():
                r = c.get(url)
                r.raise_for_status()
                out[key] = r.json()["data"]
        return json.dumps(out, separators=(",", ":")).encode()

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        d = json.loads(raw)
        today = (ts or datetime.fromisoformat(d["fetched"])).date()
        day = d["day"]
        authors = _points(d["authors"])
        open_closed = _points(d["open_closed"])
        if len(day) < MIN_DAY_ROWS:
            raise ValueError(f"rankings/models?view=day returned {len(day)} rows; endpoint changed?")
        if len(authors) < MIN_WEEKS or len(open_closed) < MIN_WEEKS:
            raise ValueError(f"weekly series too short: authors={len(authors)} open_closed={len(open_closed)}")
        rows = day_rows(self.name, day)
        rows += weekly_rows(self.name, authors, today, AUTHOR_RENAME)
        rows += weekly_rows(self.name, open_closed, today, OPEN_CLOSED_RENAME)
        return rows
