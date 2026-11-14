"""Shared fixtures: tiny synthetic price frames shaped like prices_clean.parquet."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

# Real consecutive NYSE sessions: 07-04 is a holiday and 07-06/07 a weekend, so a
# 5-session window from 07-01 ends on 07-09.
SESSIONS = [
    "2024-07-01", "2024-07-02", "2024-07-03", "2024-07-05", "2024-07-08",
    "2024-07-09", "2024-07-10", "2024-07-11", "2024-07-12",
]  # fmt: skip


def _prices(ticker: str, dates: list[str], closes: list[float], bad: set[int] = frozenset()) -> pd.DataFrame:
    closes = [np.nan if i in bad else float(c) for i, c in enumerate(closes)]
    return pd.DataFrame(
        {
            "date": pd.to_datetime(dates),
            "ticker": ticker,
            "adj_close": closes,
            "bad_bar": [i in bad for i in range(len(dates))],
        }
    )


@pytest.fixture
def sessions() -> list[str]:
    return list(SESSIONS)


@pytest.fixture
def make_prices():
    """Factory: make_prices(ticker, dates, closes, bad={row indexes}) -> frame."""
    return _prices


@pytest.fixture
def two_tickers():
    """AAA rises 1/day (r5 from 07-01 = +5%), BBB is flat (r5 = 0)."""
    return pd.concat(
        [
            _prices("AAA", SESSIONS, [100 + i for i in range(len(SESSIONS))]),
            _prices("BBB", SESSIONS, [50.0] * len(SESSIONS)),
        ],
        ignore_index=True,
    )
