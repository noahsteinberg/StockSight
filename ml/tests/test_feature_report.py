"""The feature report must never compute validation or test outcomes."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stocksight_data.feature_report import benjamini_hochberg, train_label_frame
from stocksight_data.trading_calendar import sessions_between


@pytest.fixture
def prices_across_boundary():
    days = sessions_between(pd.Timestamp("2018-10-01"), pd.Timestamp("2019-03-29"))
    rng = np.random.default_rng(0)
    frames = [
        pd.DataFrame(
            {
                "date": days,
                "ticker": t,
                "adj_close": 100 * np.cumprod(1 + rng.normal(0, 0.02, len(days))),
                "bad_bar": False,
            }
        )
        for t in ["AAA", "BBB", "CCC"]
    ]
    return pd.concat(frames, ignore_index=True)


def test_train_labels_end_before_validation(prices_across_boundary):
    labels = train_label_frame(prices_across_boundary, min_tickers=1)
    assert labels["date"].max() <= pd.Timestamp("2018-12-21")  # last as_of whose t+5 is 2018-12-31
    assert set(labels.columns) == {"ticker", "date", "excess_ret"}


def test_validation_prices_cannot_influence_the_report(prices_across_boundary):
    before = train_label_frame(prices_across_boundary, min_tickers=1)
    changed = prices_across_boundary.copy()
    later = changed["date"] > pd.Timestamp("2018-12-31")
    changed.loc[later, "adj_close"] *= np.random.default_rng(1).uniform(0.5, 2.0, later.sum())
    pd.testing.assert_frame_equal(before, train_label_frame(changed, min_tickers=1), check_exact=True)


def test_benjamini_hochberg():
    p = {"a": 0.001, "b": 0.012, "c": 0.03, "d": 0.2, "e": 0.9}
    # thresholds q*k/m = 0.01, 0.02, 0.03, 0.04, 0.05: a, b and c pass (c: 0.03 <= 0.03)
    assert benjamini_hochberg(p) == {"a": True, "b": True, "c": True, "d": False, "e": False}
    assert benjamini_hochberg({"x": 0.04, "y": 0.04}) == {"x": True, "y": True}
