"""One-time back-fill of the Bank of Korea export price indexes (see aiind/collectors/ecos.py).

The daily collector only asks for the last ten months. This pages backwards in
ten-month windows, which is what the public demo key allows per call.

    python scripts/backfill_ecos.py                 # since 2000-01
    python scripts/backfill_ecos.py --since 2015-01
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, datetime, timezone

import httpx

from aiind.collectors.base import GENERIC_USER_AGENT
from aiind.collectors.ecos import SERIES, WINDOW, Ecos, fetch_window, shift_month, to_rows
from aiind.store import append_rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2000-01", help="first month, YYYY-MM")
    ap.add_argument("--sleep", type=float, default=0.3, help="seconds between requests")
    args = ap.parse_args(argv)

    first = datetime.strptime(args.since, "%Y-%m").date()
    last = datetime.now(timezone.utc).date().replace(day=1)
    rows = []
    with httpx.Client(timeout=60, headers={"User-Agent": GENERIC_USER_AGENT}, follow_redirects=True) as c:
        for entity in SERIES:
            n = 0
            start = first
            while start <= last:
                end = min(shift_month(start, WINDOW - 1), last)
                got = to_rows(Ecos.name, entity, fetch_window(c, entity, start, end))
                rows += got
                n += len(got)
                start = shift_month(end, 1)
                time.sleep(args.sleep)
            print(f"{entity}: {n} months")
    added, total = append_rows(rows)
    print(f"rows={len(rows)} added={added} total={total}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
