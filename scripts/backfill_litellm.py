"""Back-fill token prices from the git history of LiteLLM's price file.

Lists every commit touching model_prices_and_context_window.json, keeps the
last commit of each ISO week, downloads that blob from raw.githubusercontent
(cached locally outside the repo) and replays it through the LiteLLM parser
with the commit date as the observation time.

    python scripts/backfill_litellm.py [--since 2024-01-01] [--cache DIR]

Needs a GitHub token for the commit listing (GITHUB_TOKEN env or `gh auth token`).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aiind.collectors.litellm import LiteLLM  # noqa: E402
from aiind.store import append_rows  # noqa: E402

REPO = "BerriAI/litellm"
PATH = "model_prices_and_context_window.json"


def token() -> str | None:
    if os.environ.get("GITHUB_TOKEN"):
        return os.environ["GITHUB_TOKEN"]
    try:
        return subprocess.check_output(["gh", "auth", "token"], text=True).strip()
    except Exception:
        return None


def list_commits(c: httpx.Client, since: str) -> list[tuple[str, datetime]]:
    out = []
    page = 1
    while True:
        r = c.get(
            f"https://api.github.com/repos/{REPO}/commits",
            params={"path": PATH, "per_page": 100, "page": page, "since": f"{since}T00:00:00Z"},
        )
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        for it in batch:
            d = datetime.fromisoformat(it["commit"]["committer"]["date"].replace("Z", "+00:00"))
            out.append((it["sha"], d))
        page += 1
    return out


def weekly(commits: list[tuple[str, datetime]]) -> list[tuple[str, datetime]]:
    by_week: dict[tuple[int, int], tuple[str, datetime]] = {}
    for sha, d in commits:
        k = d.isocalendar()[:2]
        if k not in by_week or d > by_week[k][1]:
            by_week[k] = (sha, d)
    return sorted(by_week.values(), key=lambda x: x[1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2024-01-01")
    ap.add_argument("--cache", default=os.environ.get("AIIND_CACHE", str(Path.home() / ".cache" / "aiind" / "litellm")))
    args = ap.parse_args()
    cache = Path(args.cache)
    cache.mkdir(parents=True, exist_ok=True)

    headers = {"User-Agent": "ai-indicators backfill", "Accept": "application/vnd.github+json"}
    tok = token()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    parser = LiteLLM()
    with httpx.Client(timeout=120, headers=headers, follow_redirects=True) as c:
        commits = list_commits(c, args.since)
        picks = weekly(commits)
        print(f"{len(commits)} commits since {args.since}; sampling {len(picks)} weekly snapshots", flush=True)
        total_rows = 0
        for i, (sha, d) in enumerate(picks, 1):
            f = cache / f"{sha}.json"
            if not f.exists():
                r = c.get(f"https://raw.githubusercontent.com/{REPO}/{sha}/{PATH}", headers={"Accept": "*/*"})
                if r.status_code != 200:
                    print(f"  skip {sha[:8]} {d.date()} http {r.status_code}", flush=True)
                    continue
                f.write_bytes(r.content)
            try:
                rows = parser.parse(f.read_bytes(), ts=d.replace(hour=12, minute=0, second=0, microsecond=0))
            except Exception as e:  # malformed historical file: skip, keep going
                print(f"  skip {sha[:8]} {d.date()} parse error {e}", flush=True)
                continue
            added, total = append_rows(rows)
            total_rows += added
            print(f"  [{i}/{len(picks)}] {d.date()} {sha[:8]} rows={len(rows)} added={added} total={total}", flush=True)
    print(f"done, added {total_rows} rows")
    return 0


if __name__ == "__main__":
    sys.exit(main())
