from __future__ import annotations

import abc
from datetime import datetime
from typing import Any

import httpx

from ..model import Row

USER_AGENT = "ai-indicators/0.1 (personal research dashboard; contact aofo.uae@gmail.com)"


# Client name without contact details, for sources that need no contact address
# (only SEC EDGAR asks for one) or that reject longer descriptive strings.
GENERIC_USER_AGENT = "ai-indicators/0.1"


class Collector(abc.ABC):
    """A collector fetches one external source and turns it into rows.

    `fetch` does I/O and returns the raw payload (bytes). `parse` is pure and
    testable against a saved raw file; `ts` overrides the observation time
    (used by back-fill scripts that replay historical snapshots). `raw_name`
    is the file written to data/raw/.
    """

    name: str
    raw_name: str
    timeout: float = 60.0
    user_agent: str = USER_AGENT

    def client(self) -> httpx.Client:
        return httpx.Client(
            timeout=self.timeout,
            headers={"User-Agent": self.user_agent, "Accept": "application/json, text/csv, text/html;q=0.5"},
            follow_redirects=True,
        )

    @abc.abstractmethod
    def fetch(self) -> bytes: ...

    @abc.abstractmethod
    def parse(self, raw: bytes, ts: datetime | None = None) -> list[Row]: ...


def fnum(x: Any) -> float | None:
    """Parse a number that may arrive as str/None; returns None when missing."""
    if x is None or x == "":
        return None
    try:
        return float(str(x).replace(",", ""))
    except (TypeError, ValueError):
        return None
