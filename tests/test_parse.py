"""Parse the committed raw snapshots; catches schema drift without network."""
from pathlib import Path

import pytest

from aiind.collectors import REGISTRY
from aiind.store import RAW

RAW_FILES = {name: RAW / cls.raw_name for name, cls in REGISTRY.items()}


@pytest.mark.parametrize("name", sorted(REGISTRY))
def test_parse_raw(name: str):
    path: Path = RAW_FILES[name]
    if not path.exists():
        pytest.skip(f"no raw snapshot for {name}")
    rows = REGISTRY[name]().parse(path.read_bytes())
    assert rows, f"{name} parsed zero rows"
    for r in rows:
        assert r.value >= 0
        assert r.unit
        assert r.entity and r.metric


def test_openrouter_sonnet_price():
    path = RAW_FILES["openrouter"]
    if not path.exists():
        pytest.skip("no raw snapshot")
    rows = REGISTRY["openrouter"]().parse(path.read_bytes())
    by = {(r.entity, r.metric): r.value for r in rows}
    # $/token * 1e6 -> $/1M; Sonnet 5.5 list price is 2 / 10
    assert by[("anthropic/claude-sonnet-5.5", "input")] == pytest.approx(2.0)
    assert by[("anthropic/claude-sonnet-5.5", "output")] == pytest.approx(10.0)
