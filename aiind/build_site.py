"""Turn data/series.parquet (+ the OpenRouter raw snapshot) into site/data/dashboard.json.

Everything derived (tier chains, ratios, rolling means, price-change events,
release cadence, capex by calendar quarter) is computed here, so the browser
only draws.

    python -m aiind.build_site
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone

from .basket import CLOSED, OPEN_WEIGHT, OPENROUTER_OPEN_WEIGHT, TIERS, VENDOR_LABEL
from .store import RAW, ROOT, load_series

SITE_DATA = ROOT / "site" / "data"
Pt = tuple[str, float]  # (iso date, value)

BIG_LABS = {"openai", "anthropic", "google", "x-ai", "deepseek", "moonshotai", "qwen", "z-ai", "minimax", "meta-llama", "mistralai"}


# ----------------------------------------------------------------- helpers
def source_map(df, source: str) -> dict[tuple[str, str], list[Pt]]:
    out: dict[tuple[str, str], list[Pt]] = defaultdict(list)
    sub = df.filter(df["source"] == source).sort("date")
    for r in sub.iter_rows(named=True):
        out[(r["entity"], r["metric"])].append((r["date"].isoformat(), r["value"]))
    return out


def line(name: str, pts: list[Pt], **extra) -> dict:
    return {"name": name, "x": [p[0] for p in pts], "y": [p[1] for p in pts], **extra}


def latest(pts: list[Pt]) -> Pt | None:
    return pts[-1] if pts else None


def value_at(pts: list[Pt], day: date) -> float | None:
    """Last value on or before `day`."""
    iso = day.isoformat()
    best = None
    for d, v in pts:
        if d <= iso:
            best = v
        else:
            break
    return best


def pct_change(pts: list[Pt], days: int) -> float | None:
    if not pts:
        return None
    d_last = date.fromisoformat(pts[-1][0])
    base = value_at(pts, d_last - timedelta(days=days))
    if base in (None, 0):
        return None
    return (pts[-1][1] / base - 1) * 100


def rolling_mean(pts: list[Pt], window: int = 7) -> list[Pt]:
    out = []
    for i in range(len(pts)):
        chunk = [v for _, v in pts[max(0, i - window + 1) : i + 1]]
        out.append((pts[i][0], sum(chunk) / len(chunk)))
    return out


def ratio(a: list[Pt], b: list[Pt]) -> list[Pt]:
    bm = dict(b)
    return [(d, v / bm[d]) for d, v in a if d in bm and bm[d]]


def since(pts: list[Pt], start: str) -> list[Pt]:
    return [p for p in pts if p[0] >= start]


# ----------------------------------------------------------------- tokens
def tier_series(lite: dict, vendor: str, tier: str, metric: str) -> tuple[list[Pt], list[str]]:
    chain = TIERS.get(vendor, {}).get(tier, [])
    maps = [(k, dict(lite.get((k, metric), []))) for k in chain]
    dates = sorted({d for _, m in maps for d in m})
    pts, models = [], []
    for d in dates:
        for k, m in reversed(maps):
            v = m.get(d)
            if v and v > 0:
                pts.append((d, v))
                models.append(k)
                break
    return pts, models


def tier_chart(lite: dict, tier: str, vendors: list[str], metric: str = "output") -> list[dict]:
    lines = []
    for v in vendors:
        pts, models = tier_series(lite, v, tier, metric)
        if pts:
            lines.append(line(VENDOR_LABEL[v], pts, text=models))
    return lines


def price_events(lite: dict) -> list[dict]:
    events = []
    for vendor, tiers in TIERS.items():
        for tier, chain in tiers.items():
            for key in chain:
                for metric in ("input", "output"):
                    pts = lite.get((key, metric), [])
                    for (d1, v1), (d2, v2) in zip(pts, pts[1:]):
                        if v1 > 0 and v2 > 0 and abs(v2 / v1 - 1) >= 0.01:
                            events.append(
                                {
                                    "date": d2,
                                    "prev_date": d1,
                                    "vendor": VENDOR_LABEL[vendor],
                                    "tier": tier,
                                    "model": key,
                                    "metric": metric,
                                    "old": v1,
                                    "new": v2,
                                    "pct": (v2 / v1 - 1) * 100,
                                }
                            )
    events.sort(key=lambda e: e["date"], reverse=True)
    return events[:60]


def release_cadence() -> dict:
    f = RAW / "openrouter_models.json"
    if not f.exists():
        return {}
    models = json.loads(f.read_bytes())["data"]
    total: dict[str, int] = defaultdict(int)
    labs: dict[str, int] = defaultdict(int)
    for m in models:
        if ":" in m["id"] or not m.get("created"):
            continue
        month = datetime.fromtimestamp(m["created"], tz=timezone.utc).strftime("%Y-%m")
        if month < "2023-08":
            continue
        total[month] += 1
        if m["id"].split("/")[0] in BIG_LABS:
            labs[month] += 1
    months = sorted(total)
    return {
        "lines": [
            {"name": "Все авторы", "x": months, "y": [total[m] for m in months]},
            {"name": "Крупные лаборатории", "x": months, "y": [labs[m] for m in months]},
        ]
    }


# ----------------------------------------------------------------- capex
def quarter_label(d: str) -> str:
    y, m = int(d[:4]), int(d[5:7])
    return f"{y}Q{(m - 1) // 3 + 1}"


def capex_chart(edgar: dict) -> dict:
    companies = ["MSFT", "GOOGL", "META", "AMZN", "ORCL"]
    by_q: dict[str, dict[str, float]] = defaultdict(dict)
    for c in companies:
        for d, v in edgar.get((c, "capex_q"), []):
            if d >= "2021-01-01":
                by_q[quarter_label(d)][c] = v / 1e9
    quarters = sorted(by_q)
    # drop the trailing quarter if fewer than 3 companies reported yet (partial)
    while quarters and len(by_q[quarters[-1]]) < 3:
        quarters.pop()
    lines = [{"name": c, "x": quarters, "y": [by_q[q].get(c) for q in quarters]} for c in companies]
    total = [sum(v for v in by_q[q].values()) for q in quarters]
    yoy = [None] * len(total)
    for i in range(4, len(total)):
        if total[i - 4]:
            yoy[i] = (total[i] / total[i - 4] - 1) * 100
    return {"lines": lines, "total": {"x": quarters, "y": total, "yoy": yoy}}


# ----------------------------------------------------------------- main
def build() -> dict:
    df = load_series()
    today = datetime.now(timezone.utc).date()
    one_year = (today - timedelta(days=365)).isoformat()
    two_years = (today - timedelta(days=730)).isoformat()

    gph = source_map(df, "gpuperhour")
    ornn = source_map(df, "ornn")
    runpod = source_map(df, "runpod")
    lite = source_map(df, "litellm")
    orep = source_map(df, "openrouter_endpoints")
    tsmc = source_map(df, "tsmc")
    edgar = source_map(df, "edgar")
    yahoo = source_map(df, "yahoo")
    fred = source_map(df, "fred")
    pypi = source_map(df, "pypistats")
    npm = source_map(df, "npm")

    ind: dict[str, dict] = {}

    # --- Compute
    h100_med = gph.get(("h100_sxm", "median"), [])
    ind["gpu_h100"] = {
        "lines": [
            line("gpuperhour, медиана", h100_med),
            line("gpuperhour, минимум", gph.get(("h100_sxm", "min"), [])),
            line("Ornn OCPI, индекс сделок", ornn.get(("h100_sxm", "index"), [])),
            line("RunPod, list secure", runpod.get(("h100_sxm", "secure"), [])),
        ]
    }
    gpus = [("h100_pcie", "H100 PCIe"), ("h100_sxm", "H100 SXM"), ("h200", "H200"), ("b200", "B200"), ("b300", "B300")]
    ind["gpu_ladder"] = {
        "categories": [lbl for _, lbl in gpus],
        "bars": [
            {"name": "gpuperhour, медиана", "y": [(latest(gph.get((g, "median"), [])) or (None, None))[1] for g, _ in gpus]},
            {"name": "RunPod, secure", "y": [(latest(runpod.get((g, "secure"), [])) or (None, None))[1] for g, _ in gpus]},
            {"name": "Ornn, индекс", "y": [(latest(ornn.get((g, "index"), [])) or (None, None))[1] for g, _ in gpus]},
        ],
    }
    ind["gpu_gen_ratio"] = {
        "lines": [
            line("B200 / H100 SXM", ratio(gph.get(("b200", "median"), []), h100_med)),
            line("H200 / H100 SXM", ratio(gph.get(("h200", "median"), []), h100_med)),
            line("B300 / H100 SXM", ratio(gph.get(("b300", "median"), []), h100_med)),
        ]
    }
    ind["gpu_depth"] = {
        "lines": [
            line("H100 SXM", gph.get(("h100_sxm", "providers"), [])),
            line("H200", gph.get(("h200", "providers"), [])),
            line("B200", gph.get(("b200", "providers"), [])),
        ]
    }

    # --- Tokens
    ind["tok_frontier"] = {"lines": tier_chart(lite, "frontier", CLOSED + ["deepseek", "moonshot", "qwen"])}
    ind["tok_mid"] = {"lines": tier_chart(lite, "mid", ["openai", "anthropic", "google", "mistral"])}
    ind["tok_small"] = {"lines": tier_chart(lite, "small", ["openai", "anthropic", "google", "deepseek", "qwen", "mistral"])}
    ind["tok_frontier_input"] = {"lines": tier_chart(lite, "frontier", CLOSED + ["deepseek", "moonshot"], metric="input")}

    closed_mid = [tier_series(lite, v, "mid", "output")[0] for v in ("openai", "anthropic", "google")]
    closed_dates = sorted(set.intersection(*[set(dict(p)) for p in closed_mid if p])) if all(closed_mid) else []
    mid_mean = [(d, statistics.mean(dict(p)[d] for p in closed_mid)) for d in closed_dates]
    disc_lines = []
    for v in ("deepseek", "moonshot", "qwen", "minimax"):
        pts, _ = tier_series(lite, v, "frontier", "output")
        r = ratio(pts, mid_mean)
        if r:
            disc_lines.append(line(VENDOR_LABEL[v], r))
    ind["tok_open_discount"] = {"lines": disc_lines}

    market = []
    for mid in OPENROUTER_OPEN_WEIGHT:
        prov = latest(orep.get((mid, "providers"), []))
        if not prov:
            continue
        market.append(
            {
                "model": mid,
                "providers": int(prov[1]),
                "min_output": (latest(orep.get((mid, "min_output"), [])) or (0, None))[1],
                "median_output": (latest(orep.get((mid, "median_output"), [])) or (0, None))[1],
                "fp_output": (latest(orep.get((mid, "fp_output"), [])) or (0, None))[1],
                "date": prov[0],
            }
        )
    ind["tok_or_market"] = {"rows": market}
    ind["tok_events"] = {"rows": price_events(lite)}
    ind["tok_releases"] = release_cadence()

    # --- Supply chain, capex, markets
    rev = tsmc.get(("TSMC", "revenue_ntd_m"), [])
    yoy = []
    rev_map = dict(rev)
    for d, v in rev:
        prev = f"{int(d[:4]) - 1}{d[4:]}"
        yoy.append((v / rev_map[prev] - 1) * 100 if rev_map.get(prev) else None)
    ind["tsmc_rev"] = {"bars": {"x": [d[:7] for d, _ in rev], "y": [v / 1000 for _, v in rev], "yoy": yoy}}
    ind["capex"] = capex_chart(edgar)

    eq_lines = []
    for t in ["NVDA", "SMH", "SPY", "TSM", "MU", "CRWV", "ORCL"]:
        pts = since(yahoo.get((t, "close"), []), one_year)
        if pts:
            base = pts[0][1]
            eq_lines.append(line(t, [(d, v / base * 100) for d, v in pts]))
    ind["equity"] = {"lines": eq_lines}
    ind["credit"] = {"lines": [line("HY OAS, %", since(fred.get(("BAMLH0A0HYM2", "hy_oas"), []), two_years))]}
    ind["gas"] = {"lines": [line("Henry Hub, $/MMBtu", since(fred.get(("DHHNGSP", "henry_hub"), []), two_years))]}

    # --- Adoption
    ind["pypi"] = {"lines": [line(p, rolling_mean(pypi.get((p, "downloads"), []))) for p in ["openai", "anthropic", "litellm", "google-genai", "langchain", "mcp"] if pypi.get((p, "downloads"))]}
    ind["npm"] = {"lines": [line(p, rolling_mean(npm.get((p, "downloads"), []))) for p in ["openai", "@anthropic-ai/sdk", "ai", "@google/genai", "@modelcontextprotocol/sdk"] if npm.get((p, "downloads"))]}

    # --- Overview tiles
    fr = [tier_series(lite, v, "frontier", "output")[0] for v in ("openai", "anthropic", "google")]
    fr_dates = sorted(set.intersection(*[set(dict(p)) for p in fr if p])) if all(fr) else []
    fr_mean = [(d, statistics.mean(dict(p)[d] for p in fr)) for d in fr_dates]
    nvda = yahoo.get(("NVDA", "close"), [])
    hy = fred.get(("BAMLH0A0HYM2", "hy_oas"), [])
    b200_ratio = ratio(gph.get(("b200", "median"), []), h100_med)
    ds_disc = next((l for l in disc_lines if l["name"] == VENDOR_LABEL["deepseek"]), None)
    cap = ind["capex"]["total"]
    pypi_ai = rolling_mean([(d, a + b) for (d, a), (_, b) in zip(pypi.get(("openai", "downloads"), []), pypi.get(("anthropic", "downloads"), []))]) if pypi.get(("anthropic", "downloads")) else []

    def tile(id_, label, pts, unit, days=30, note=None):
        lv = latest(pts)
        return {
            "id": id_,
            "label": label,
            "value": lv[1] if lv else None,
            "date": lv[0] if lv else None,
            "unit": unit,
            "delta_pct": pct_change(pts, days),
            "delta_days": days,
            "note": note,
        }

    tiles = [
        tile("h100", "H100 SXM, аренда", h100_med, "usd_h", 30, "медиана gpuperhour"),
        tile("b200r", "B200 / H100", b200_ratio, "x", 30, "во сколько раз дороже"),
        tile("frontier", "Frontier, output", fr_mean, "usd_mtok", 90, "среднее OpenAI/Anthropic/Google"),
        tile("mid", "Mid-tier, output", mid_mean, "usd_mtok", 90, "среднее OpenAI/Anthropic/Google"),
        tile("ds", "DeepSeek vs mid-tier", ds_disc["x"] and list(zip(ds_disc["x"], ds_disc["y"])) if ds_disc else [], "x", 90, "цена DeepSeek / mid-tier"),
        {"id": "tsmc", "label": "TSMC, выручка YoY", "value": yoy[-1] if yoy else None, "date": rev[-1][0][:7] if rev else None, "unit": "pct", "delta_pct": None, "note": "последний месяц"},
        {"id": "capex", "label": "Capex 5 hyperscalers", "value": cap["y"][-1] if cap["y"] else None, "date": cap["x"][-1] if cap["x"] else None, "unit": "usd_b", "delta_pct": cap["yoy"][-1] if cap["yoy"] else None, "delta_days": 365, "note": "за квартал, $ млрд"},
        tile("nvda", "NVDA", nvda, "usd", 30),
        tile("hy", "HY спред", hy, "pct", 30, "ICE BofA OAS"),
        tile("pypi", "PyPI openai+anthropic", pypi_ai, "count", 30, "скачиваний в день, 7д среднее"),
    ]

    status_file = ROOT / "data" / "run_status.json"
    status = json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {}

    return {
        "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "rows": df.height,
        "status": status,
        "tiles": tiles,
        "indicators": ind,
    }


def main() -> int:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    out = build()
    (SITE_DATA / "dashboard.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"dashboard.json: {len(out['indicators'])} indicators, {out['rows']} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
