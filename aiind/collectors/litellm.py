"""LiteLLM model_prices_and_context_window.json: broad price table, $/token.

We keep the raw file whole (git history gives free back-fill) but only emit
series for first-party chat models of the vendors we track, to avoid
thousands of reseller rows (bedrock/, azure/, vertex_ai/...).
"""
from __future__ import annotations

import json
from datetime import datetime

from ..model import USD_PER_MTOK, Row, now_utc
from .base import Collector, fnum

URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"

PROVIDERS = {
    "openai",
    "anthropic",
    "deepseek",
    "gemini",
    "xai",
    "mistral",
    "moonshot",
    "dashscope",
    "zai",
    "minimax",
}
MODES = {"chat", "responses"}

METRICS = {
    "input_cost_per_token": "input",
    "output_cost_per_token": "output",
    "cache_read_input_token_cost": "cache_read",
    "cache_creation_input_token_cost": "cache_write",
}


class LiteLLM(Collector):
    name = "litellm"
    raw_name = "litellm.json"

    def fetch(self) -> bytes:
        with self.client() as c:
            r = c.get(URL)
            r.raise_for_status()
            return r.content

    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]:
        ts = ts or now_utc()
        rows: list[Row] = []
        for key, m in json.loads(raw).items():
            if key == "sample_spec" or not isinstance(m, dict):
                continue
            if m.get("litellm_provider") not in PROVIDERS or m.get("mode") not in MODES:
                continue
            meta = {
                "provider": m.get("litellm_provider"),
                "max_input_tokens": m.get("max_input_tokens"),
                "deprecation_date": m.get("deprecation_date"),
            }
            for field, metric in METRICS.items():
                v = fnum(m.get(field))
                if v is None:
                    continue
                rows.append(
                    Row(ts=ts, source=self.name, entity=key, metric=metric, value=v * 1_000_000, unit=USD_PER_MTOK, meta=meta)
                )
        return rows
