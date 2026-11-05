"""One-time back-fill of OpenRouter per-model daily usage from stats/model-activity.

The daily collector only sees yesterday; this endpoint returns the last 30
complete days (plus the partial current day, dropped) per model variant. One
request per variant listed in the 30-day ranking (~750), throttled.

    python scripts/backfill_openrouter_activity.py            # all variants
    python scripts/backfill_openrouter_activity.py --limit 20 # smoke test
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

import httpx

from aiind.collectors.base import USER_AGENT
from aiind.collectors.openrouter_usage import BASE, OpenRouterUsage, day_rows, usage_entity
from aiind.store import append_rows

ACTIVITY = f"{BASE}/stats/model-activity"


def activity(c: httpx.Client, slug: str, variant: str) -> list[dict]:
    params = {"permaslug": slug}
    if variant != "standard":
        params["variant"] = variant
    r = c.get(ACTIVITY, params=params)
    r.raise_for_status()
    recs = r.json()["data"]["analytics"]
    for rec in recs:  # make the identity explicit; the endpoint echoes it but do not rely on that
        rec["model_permaslug"] = slug
        rec["variant"] = variant
    return recs


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="only the first N variants (smoke test)")
    ap.add_argument("--sleep", type=float, default=0.3, help="seconds between requests")
    args = ap.parse_args(argv)

    today = datetime.now(timezone.utc).date().isoformat()
    total_rows = 0
    empty: list[str] = []
    failed: list[str] = []
    with httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as c:
        r = c.get(f"{BASE}/rankings/models?view=month")
        r.raise_for_status()
        variants = [(m["model_permaslug"], m.get("variant") or "standard") for m in r.json()["data"]]
        if args.limit:
            variants = variants[: args.limit]
        print(f"{len(variants)} model variants in the 30-day ranking")
        batch = []
        for i, (slug, variant) in enumerate(variants, 1):
            ent = usage_entity(slug, variant)
            try:
                recs = [x for x in activity(c, slug, variant) if x["date"][:10] < today]
            except httpx.HTTPError as e:
                failed.append(ent)
                print(f"  {ent}: {e}", file=sys.stderr)
                continue
            if not recs:
                empty.append(ent)
            batch += day_rows(OpenRouterUsage.name, recs)
            if len(batch) >= 20000 or i == len(variants):
                added, total = append_rows(batch)
                total_rows += len(batch)
                print(f"[{i}/{len(variants)}] rows={len(batch)} added={added} total={total}")
                batch = []
            time.sleep(args.sleep)
    print(f"done: {total_rows} rows; {len(empty)} variants with no history; {len(failed)} failed")
    if empty[:10]:
        print("  no history:", ", ".join(empty[:10]), "..." if len(empty) > 10 else "")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
