from __future__ import annotations

import os
from pathlib import Path

import polars as pl

from .model import Row

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW = DATA / "raw"
SERIES = DATA / "series.parquet"

SCHEMA = {
    "date": pl.Date,
    "ts": pl.Datetime("us"),
    "source": pl.Utf8,
    "entity": pl.Utf8,
    "metric": pl.Utf8,
    "value": pl.Float64,
    "unit": pl.Utf8,
    "meta": pl.Utf8,
}
KEY = ["date", "source", "entity", "metric"]


def save_raw(name: str, content: bytes | str) -> Path:
    """Overwrite data/raw/<name>. History lives in git, not in dated folders,
    so the working tree stays small and git delta-compresses the daily diffs."""
    RAW.mkdir(parents=True, exist_ok=True)
    path = RAW / name
    if isinstance(content, str):
        content = content.encode("utf-8")
    path.write_bytes(content)
    return path


def load_series() -> pl.DataFrame:
    if SERIES.exists():
        return pl.read_parquet(SERIES)
    return pl.DataFrame(schema=SCHEMA)


def append_rows(rows: list[Row]) -> tuple[int, int]:
    """Merge rows into series.parquet. Returns (rows_added, total_rows)."""
    if not rows:
        return 0, load_series().height
    new = pl.DataFrame([r.to_record() for r in rows], schema=SCHEMA)
    old = load_series()
    before = old.height
    merged = (
        pl.concat([old, new], how="vertical")
        .sort("ts")
        .unique(subset=KEY, keep="last", maintain_order=True)
        .sort(["date", "source", "entity", "metric"])
    )
    DATA.mkdir(parents=True, exist_ok=True)
    tmp = SERIES.with_suffix(".parquet.tmp")
    merged.write_parquet(tmp, compression="zstd")
    os.replace(tmp, SERIES)  # atomic swap so readers never see a partial file
    return merged.height - before, merged.height
