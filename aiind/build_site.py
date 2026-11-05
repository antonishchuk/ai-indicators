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

from .basket import CLOSED, OPEN_WEIGHT, OPENROUTER_AUTHOR_LABEL, OPENROUTER_OPEN_WEIGHT, TIERS, VENDOR_LABEL
from .collectors.openrouter_usage import split_entity
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


# ----------------------------------------------------------------- OpenRouter usage (demand)
SPEND_VENDORS = ["openai", "anthropic", "google", "x-ai", "deepseek", "moonshotai", "z-ai", "qwen", "minimax"]
GROWTH_VENDORS = ["openai", "anthropic", "google", "deepseek"]
SHARE_VENDORS = ["deepseek", "openai", "anthropic", "google", "z-ai", "x-ai"]
TRILLION = 1e12


def author_label(slug: str) -> str:
    return OPENROUTER_AUTHOR_LABEL.get(slug, slug)


def canonical_ids() -> dict[str, str]:
    """OpenRouter canonical (dated) permaslug -> model id of the standard variant, from the raw snapshot.
    Usage rows are keyed by permaslug, prices by id; 97% of tokens map this way."""
    f = RAW / "openrouter_models.json"
    out: dict[str, str] = {}
    if f.exists():
        for m in json.loads(f.read_bytes())["data"]:
            if ":" not in m["id"] and m.get("canonical_slug"):
                out[m["canonical_slug"]] = m["id"]
    return out


def price_on(orp: dict, pid: str, metric: str, day: str) -> float | None:
    """OpenRouter $/1M on `day`; before the first price snapshot the earliest known price is used."""
    pts = orp.get((pid, metric), [])
    if not pts:
        return None
    v = value_at(pts, date.fromisoformat(day))
    return pts[0][1] if v is None else v


def spend_by_vendor(oru: dict, orp: dict, canon: dict[str, str]) -> tuple[dict, dict, dict]:
    """Estimated $ per vendor per day = tokens x cheapest routed OpenRouter price of that day.
    Cached prompt tokens at the cache-read price, free variants at zero, batch at half list when unlisted.
    Returns (usd[vendor][day], tokens[day], priced_tokens[day])."""
    usage: dict[str, dict[str, dict[str, float]]] = defaultdict(lambda: defaultdict(dict))
    for (entity, metric), pts in oru.items():
        if metric in ("prompt_tokens", "completion_tokens", "cached_tokens"):
            for d, v in pts:
                usage[entity][d][metric] = v
    usd: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    tokens: dict[str, float] = defaultdict(float)
    priced: dict[str, float] = defaultdict(float)
    for entity, days in usage.items():
        slug, variant = split_entity(entity)
        vendor = slug.split("/")[0]
        base = canon.get(slug)
        for d, m in days.items():
            prompt = m.get("prompt_tokens", 0.0)
            comp = m.get("completion_tokens", 0.0)
            cached = min(m.get("cached_tokens", 0.0), prompt)
            tokens[d] += prompt + comp
            if variant == "free":
                priced[d] += prompt + comp
                continue
            if base is None:
                continue
            pid = base if variant == "standard" else f"{base}:{variant}"
            pin, pout = price_on(orp, pid, "input", d), price_on(orp, pid, "output", d)
            if pin is None and variant == "batch":
                pin, pout = price_on(orp, base, "input", d), price_on(orp, base, "output", d)
                if pin is not None:
                    pin, pout = pin * 0.5, (pout or 0.0) * 0.5
            if pin is None or pout is None:
                continue
            pcache = price_on(orp, pid, "cache_read", d)
            if pcache is None:
                pcache = pin
            usd[vendor][d] += ((prompt - cached) * pin + cached * pcache + comp * pout) / 1e6
            priced[d] += prompt + comp
    return usd, tokens, priced


def weekly_growth(pts: list[Pt], lag: int, window: int = 4) -> list[Pt]:
    """Rolling `window`-week sum vs the same sum `lag` weeks earlier, in %. Weeks are Mondays;
    a missing week (vendor out of the top 9) breaks the sums that would include it."""
    if not pts:
        return []
    start = date.fromisoformat(pts[0][0])
    n = (date.fromisoformat(pts[-1][0]) - start).days // 7 + 1
    vals: list[float | None] = [None] * n
    for d, v in pts:
        vals[(date.fromisoformat(d) - start).days // 7] = v

    def rsum(i: int) -> float | None:
        if i - window + 1 < 0:
            return None
        chunk = vals[i - window + 1 : i + 1]
        return None if any(c is None for c in chunk) else sum(chunk)

    out: list[Pt] = []
    for i in range(lag, n):
        a, b = rsum(i), rsum(i - lag)
        if a is not None and b:
            out.append(((start + timedelta(weeks=i)).isoformat(), (a / b - 1) * 100))
    return out


def usage_charts(oru: dict, orp: dict) -> tuple[dict[str, dict], list[Pt], list[Pt]]:
    """-> (indicators, total weekly tokens, total daily $ 7d mean) for the tiles."""
    ind: dict[str, dict] = {}
    # --- $ per day by vendor
    usd, tokens, priced = spend_by_vendor(oru, orp, canonical_ids())
    days = sorted(tokens)
    total_usd = [(d, sum(m.get(d, 0.0) for m in usd.values())) for d in days]
    coverage = [f"цена известна для {priced[d] / tokens[d] * 100:.0f}% токенов" if tokens[d] else "" for d in days]
    spend_lines = [line("Всего", rolling_mean(total_usd), text=coverage, ci="total")]
    for v in SPEND_VENDORS:
        pts = [(d, usd[v].get(d, 0.0)) for d in days]
        if any(y > 0 for _, y in pts):
            spend_lines.append(line(author_label(v), rolling_mean(pts)))
    rest = [(d, sum(m.get(d, 0.0) for vd, m in usd.items() if vd not in SPEND_VENDORS)) for d in days]
    if any(y > 0 for _, y in rest):
        spend_lines.append(line("Остальные", rolling_mean(rest)))
    ind["or_spend"] = {"lines": spend_lines}

    # --- weekly tokens by author: growth, share, total
    weekly = {e: pts for (e, m), pts in oru.items() if m == "tokens_week" and e not in ("open_weight", "closed")}
    weeks = sorted({d for pts in weekly.values() for d, _ in pts})
    total_week: dict[str, float] = defaultdict(float)
    for pts in weekly.values():
        for d, v in pts:
            total_week[d] += v
    for key, lag in (("or_yoy", 52), ("or_qoq", 13)):
        ind[key] = {"lines": [line(author_label(v), g, ci=VENDOR_COLOR.get(v, ci)) for ci, v in enumerate(GROWTH_VENDORS) if (g := weekly_growth(weekly.get(v, []), lag))]}
    share_lines = []
    for v in SHARE_VENDORS:
        m = dict(weekly.get(v, []))
        if m:
            share_lines.append({"name": author_label(v), "x": weeks, "y": [m[d] / total_week[d] * 100 if d in m and total_week[d] else None for d in weeks]})
    ind["or_share"] = {"lines": share_lines}
    total_pts = [(d, total_week[d] / TRILLION) for d in weeks]
    ind["or_total"] = {"lines": [line("Все модели, трлн токенов", total_pts)]}
    op, cl = dict(oru.get(("open_weight", "tokens_week"), [])), dict(oru.get(("closed", "tokens_week"), []))
    open_share = [(d, op[d] / (op[d] + cl[d]) * 100) for d in sorted(op) if d in cl and op[d] + cl[d]]
    ind["or_open"] = {"lines": [line("Open-weight, % токенов", open_share)]}
    return ind, [(d, total_week[d]) for d in weeks], rolling_mean(total_usd)


# ----------------------------------------------------------------- Ramp AI Index (token spend in $)
RAMP_LABEL = {"anthropic": "Anthropic", "openai": "OpenAI", "google": "Google", "xai": "xAI", "deepseek": "DeepSeek", "all": "Всего"}
RAMP_MAKERS = ["anthropic", "openai", "google", "xai", "deepseek"]
# one palette slot per vendor so a vendor keeps its color across the demand cards (series-1 .. series-8)
VENDOR_COLOR = {"openai": 0, "anthropic": 1, "google": 2, "xai": 3, "x-ai": 3, "deepseek": 4, "moonshotai": 5, "z-ai": 6, "all": "total"}
LOG_FLOOR_USD = 100.0  # below this a weekly amount is noise that drags a log axis to nano-dollars; shown as a gap


def floor_log(pts: list[Pt], floor: float = LOG_FLOOR_USD) -> list[Pt]:
    return [(d, v if v >= floor else None) for d, v in pts]


def ramp_charts(ramp: dict, fred: dict) -> tuple[dict[str, dict], list[Pt], list[Pt]]:
    """-> (indicators, total weekly spend, Anthropic share of spend) for the tiles."""
    ind: dict[str, dict] = {}
    spend = {e: pts for (e, m), pts in ramp.items() if m == "token_spend_week"}
    total = spend.get("all", [])
    tot = dict(total)
    lines = [line("Всего", total, ci=VENDOR_COLOR["all"])]
    for mk in RAMP_MAKERS:
        if spend.get(mk):
            lines.append(line(RAMP_LABEL[mk], floor_log(spend[mk]), ci=VENDOR_COLOR[mk]))
    named = {d: sum(dict(spend.get(mk, [])).get(d, 0.0) for mk in RAMP_MAKERS) for d in tot}
    rest = floor_log([(d, v - named[d]) for d, v in total])
    if any(v for _, v in rest):
        lines.append(line("Остальные", rest))
    ind["ramp_spend"] = {"lines": lines}
    for key, lag in (("ramp_yoy", 52), ("ramp_qoq", 13)):
        ind[key] = {"lines": [line(RAMP_LABEL[mk], g, ci=VENDOR_COLOR[mk]) for mk in ("anthropic", "openai", "all") if (g := weekly_growth(spend.get(mk, []), lag))]}
    ind["ramp_share"] = {"lines": [line(RAMP_LABEL[mk], [(d, v / tot[d] * 100) for d, v in spend[mk] if tot.get(d)], ci=VENDOR_COLOR[mk]) for mk in ("anthropic", "openai", "google", "xai") if spend.get(mk)]}
    paid = []
    for mk in ("openai", "anthropic"):
        for tt, lbl, dash in (("all_tokens", "все токены", None), ("output", "output", "dot")):
            pts = ramp.get((mk, f"paid_{tt}"), [])
            if pts:
                paid.append(line(f"{RAMP_LABEL[mk]}, {lbl}", pts, ci=VENDOR_COLOR[mk], **({"dash": dash} if dash else {})))
    ind["tok_paid"] = {"lines": paid}
    adoption = []
    for sid, lbl, ci in (("RAMPAIALL", "Все вендоры", "total"), ("RAMPAIOPENAI", "OpenAI", 0), ("RAMPAIANTHROPIC", "Anthropic", 1), ("RAMPAIXAI", "xAI", 3)):
        pts = fred.get((sid, "ai_adoption"), [])
        if pts:
            adoption.append(line(lbl, pts, ci=ci))
    ind["ramp_adoption"] = {"lines": adoption}
    anth_share = next((list(zip(l["x"], l["y"])) for l in ind["ramp_share"]["lines"] if l["name"] == "Anthropic"), [])
    return ind, total, anth_share


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
    orp = source_map(df, "openrouter")
    oru = source_map(df, "openrouter_usage")
    ramp = source_map(df, "ramp")
    tsmc = source_map(df, "tsmc")
    edgar = source_map(df, "edgar")
    fred = source_map(df, "fred")
    yahoo = source_map(df, "yahoo")
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

    # --- Demand (Ramp token spend, OpenRouter usage)
    ramp_ind, ramp_total_week, ramp_anth_share = ramp_charts(ramp, fred)
    ind.update(ramp_ind)
    usage_ind, or_total_week, or_usd_day = usage_charts(oru, orp)
    ind.update(usage_ind)

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
        tile("ramp_spend", "Ramp: расход на токены", ramp_total_week, "usd_big", 91, "$ в неделю, выборка TSM"),
        tile("ramp_anth", "Ramp: доля Anthropic", ramp_anth_share, "pct", 91, "в расходах на токены"),
        tile("or_tokens", "OpenRouter, токенов", or_total_week, "tokens", 91, "за неделю, все модели"),
        tile("or_usd", "OpenRouter, расход", or_usd_day, "usd_big", 30, "$ в день, оценка, 7д среднее"),
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
