"""RunPod public GraphQL: list prices per GPU type (secure / community cloud)."""
from __future__ import annotations

import json

from ..model import USD_PER_GPU_HOUR, Row, now_utc
from .base import Collector, fnum

URL = "https://api.runpod.io/graphql"
QUERY = "{ gpuTypes { id displayName memoryInGb securePrice communityPrice secureSpotPrice communitySpotPrice } }"

# RunPod id -> our entity slug. Anything not listed is kept in raw only.
GPUS = {
    "NVIDIA H100 80GB HBM3": "h100_sxm",
    "NVIDIA H100 PCIe": "h100_pcie",
    "NVIDIA H100 NVL": "h100_nvl",
    "NVIDIA H200": "h200",
    "NVIDIA H200 NVL": "h200_nvl",
    "NVIDIA B200": "b200",
    "NVIDIA B300 SXM6 AC": "b300",
    "NVIDIA A100 80GB PCIe": "a100_pcie",
    "NVIDIA A100-SXM4-80GB": "a100_sxm",
}

METRICS = {
    "securePrice": "secure",
    "communityPrice": "community",
    "secureSpotPrice": "secure_spot",
    "communitySpotPrice": "community_spot",
}


class RunPod(Collector):
    name = "runpod"
    raw_name = "runpod_gputypes.json"

    def fetch(self) -> bytes:
        with self.client() as c:
            r = c.post(URL, json={"query": QUERY})
            r.raise_for_status()
            return r.content

    def parse(self, raw: bytes) -> list[Row]:
        ts = now_utc()
        rows: list[Row] = []
        for g in json.loads(raw)["data"]["gpuTypes"]:
            entity = GPUS.get(g["id"])
            if not entity:
                continue
            for key, metric in METRICS.items():
                v = fnum(g.get(key))
                if v is None or v <= 0:
                    continue
                rows.append(
                    Row(
                        ts=ts,
                        source=self.name,
                        entity=entity,
                        metric=metric,
                        value=v,
                        unit=USD_PER_GPU_HOUR,
                        meta={"runpod_id": g["id"], "memory_gb": g.get("memoryInGb")},
                    )
                )
        return rows
