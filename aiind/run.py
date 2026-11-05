"""Run collectors: fetch -> save raw -> parse -> merge into series.parquet.

    python -m aiind.run                 # all collectors
    python -m aiind.run --only ornn,runpod
    python -m aiind.run --reparse       # parse data/raw/* without fetching

One failing collector does not stop the others; the exit code is non-zero if
any failed so the workflow run shows red.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import date

from .collectors import REGISTRY
from .store import DATA, RAW, append_rows, save_raw


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma-separated collector names")
    ap.add_argument("--reparse", action="store_true", help="parse saved raw files instead of fetching")
    args = ap.parse_args(argv)

    names = args.only.split(",") if args.only else list(REGISTRY)
    unknown = [n for n in names if n not in REGISTRY]
    if unknown:
        print(f"unknown collectors: {unknown}; known: {list(REGISTRY)}", file=sys.stderr)
        return 2

    failed: list[str] = []
    for name in names:
        col = REGISTRY[name]()
        t0 = time.time()
        try:
            if args.reparse:
                raw = (RAW / col.raw_name).read_bytes()
            else:
                raw = col.fetch()
                save_raw(col.raw_name, raw)
            rows = col.parse(raw)
            added, total = append_rows(rows)
            print(f"[{name}] rows={len(rows)} added={added} total={total} {time.time() - t0:.1f}s")
        except Exception:
            failed.append(name)
            print(f"[{name}] FAILED", file=sys.stderr)
            traceback.print_exc()
    status = {"date": date.today().isoformat(), "ok": [n for n in names if n not in failed], "failed": failed}
    if not args.reparse:
        DATA.mkdir(parents=True, exist_ok=True)
        (DATA / "run_status.json").write_text(json.dumps(status, indent=1), encoding="utf-8")
    if failed:
        print(f"failed: {failed}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
