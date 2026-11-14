"""5-session market-relative labels (contract 3.2, ADR-0004) and purged splits (ADR-0005)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stocksight_data.labels import (
    FUTURE_COLUMNS,
    MEMBERSHIP_COLUMNS,
    assign_split,
    build_labels,
    check_feature_columns,
    label_frame,
    trailing_excess,
)
from stocksight_data.trading_calendar import get_calendar, sessions_between


def labels_for(prices, **kw) -> pd.DataFrame:
    kw.setdefault("min_tickers", 1)
    return build_labels(prices, **kw)


def rows(labels: pd.DataFrame, ticker: str) -> pd.DataFrame:
    sub = labels[labels["ticker"] == ticker]
    return sub.set_index(sub["date"].dt.strftime("%Y-%m-%d"))


# ------------------------------------------------------------------ horizon
def test_target_is_the_fifth_session_across_holiday_and_weekend(two_tickers):
    aaa = rows(labels_for(two_tickers), "AAA")
    assert aaa.loc["2024-07-01", "target_date"] == pd.Timestamp("2024-07-09")  # skips 07-04 and the weekend
    assert aaa.loc["2024-07-01", "r5"] == pytest.approx(105 / 100 - 1)  # not 101/100 (t+1)
    assert aaa.loc["2024-07-03", "target_date"] == pd.Timestamp("2024-07-11")


def test_last_five_rows_of_each_ticker_have_no_label(two_tickers):
    labels = labels_for(two_tickers)
    for ticker in ["AAA", "BBB"]:
        assert list(rows(labels, ticker).index) == ["2024-07-01", "2024-07-02", "2024-07-03", "2024-07-05"]


def test_ret_is_the_trailing_one_day_return(two_tickers):
    aaa = rows(labels_for(two_tickers), "AAA")
    assert pd.isna(aaa.loc["2024-07-01", "ret"])  # no previous row
    assert aaa.loc["2024-07-02", "ret"] == pytest.approx(101 / 100 - 1)


# ----------------------------------------------------------- market-relative
def test_label_is_relative_to_the_equal_weight_mean(two_tickers):
    labels = labels_for(two_tickers)
    aaa, bbb = rows(labels, "AAA").loc["2024-07-01"], rows(labels, "BBB").loc["2024-07-01"]
    assert aaa["market_r5"] == pytest.approx(0.025)  # mean of +5% and 0%
    assert aaa["excess_ret"] == pytest.approx(0.025) and aaa["label"] == 1
    assert bbb["excess_ret"] == pytest.approx(-0.025) and bbb["label"] == 0


def test_equal_moves_give_zero_excess_and_tie_labels(make_prices, sessions):
    closes = [100 + i for i in range(len(sessions))]
    prices = pd.concat([make_prices("AAA", sessions, closes), make_prices("BBB", sessions, closes)])
    labels = labels_for(prices)
    assert len(labels) == 8  # rows are kept ...
    assert (labels["excess_ret"] == 0).all()
    assert labels["label"].isna().all()  # ... but every label is a tie


def test_median_benchmark_switch(make_prices, sessions):
    up = [100 + 10 * i for i in range(len(sessions))]
    flat = [100.0] * len(sessions)
    prices = pd.concat(
        [make_prices("UP", sessions, up), make_prices("F1", sessions, flat), make_prices("F2", sessions, flat)]
    )
    mean_labels = labels_for(prices, benchmark="mean")
    median_labels = labels_for(prices, benchmark="median")
    assert (rows(mean_labels, "F1")["label"] == 0).all()  # flat is below the mean
    assert rows(median_labels, "F1")["label"].isna().all()  # flat equals the median: tie
    assert (rows(median_labels, "UP")["label"] == 1).all()
    with pytest.raises(ValueError, match="benchmark"):
        labels_for(prices, benchmark="max")


# ------------------------------------------------------------------ validity
@pytest.mark.parametrize("bad_at", [0, 1, 2, 3, 4, 5], ids=lambda k: f"t+{k}")
def test_bad_bar_anywhere_in_the_window_invalidates_the_row(make_prices, sessions, bad_at):
    prices = pd.concat(
        [
            make_prices("AAA", sessions, [100 + i for i in range(len(sessions))], bad={bad_at}),
            make_prices("BBB", sessions, [50.0] * len(sessions)),
        ]
    )
    assert "2024-07-01" not in rows(labels_for(prices), "AAA").index


def test_bad_bar_just_after_the_window_does_not_invalidate(make_prices, sessions):
    prices = pd.concat(
        [
            make_prices("AAA", sessions, [100 + i for i in range(len(sessions))], bad={6}),
            make_prices("BBB", sessions, [50.0] * len(sessions)),
        ]
    )
    assert "2024-07-01" in rows(labels_for(prices), "AAA").index  # window is t..t+5 = rows 0..5


def test_missing_session_in_the_window_invalidates_the_row(make_prices, sessions):
    gappy = [d for d in sessions if d != "2024-07-08"]
    prices = pd.concat(
        [
            make_prices("AAA", gappy, [100 + i for i in range(len(gappy))]),
            make_prices("BBB", sessions, [50.0] * len(sessions)),
        ]
    )
    labels = labels_for(prices)
    assert rows(labels, "AAA").empty  # every AAA window either spans 07-08 or runs past the data
    assert len(rows(labels, "BBB")) == 4


def test_min_tickers_drops_sparse_dates(make_prices, sessions):
    prices = pd.concat(
        [
            make_prices("AAA", sessions, [100 + i for i in range(len(sessions))]),
            make_prices("BBB", sessions, [50.0] * len(sessions)),
            make_prices("CCC", sessions[2:], [10 + i for i in range(len(sessions) - 2)]),  # starts 07-03
        ]
    )
    frame = label_frame(prices, min_tickers=3)
    kept = sorted(build_labels(prices, min_tickers=3)["date"].dt.strftime("%m-%d").unique())
    assert kept == ["07-03", "07-05"]  # only dates with 3 valid tickers
    sparse = frame[frame["status"] == "sparse_date"]["date"].dt.strftime("%m-%d").unique()
    assert set(sparse) == {"07-01", "07-02"}  # 2 valid tickers each (CCC's first window is 07-03 -> 07-11)


def test_output_is_sorted_and_unique(two_tickers):
    labels = labels_for(two_tickers.iloc[::-1])
    assert labels.equals(labels.sort_values(["ticker", "date"]).reset_index(drop=True))
    assert not labels.duplicated(["ticker", "date"]).any()


# ------------------------------------------------------------------- splits
@pytest.mark.parametrize(
    "as_of,target,expected",
    [
        ("2018-12-21", "2018-12-31", "train"),
        ("2018-12-24", "2019-01-02", None),  # t+5 falls in validation
        ("2019-01-02", "2019-01-09", "validation"),
        ("2021-12-27", "2022-01-03", None),  # t+5 falls in test
        ("2022-01-03", "2022-01-10", "test"),
        ("2026-11-05", "2026-11-12", "test"),
        ("2026-11-06", "2026-11-13", None),  # t+5 after the data cutoff
    ],
    ids=["train", "train-purge", "validation", "validation-purge", "test", "test-last", "after-cutoff"],
)
def test_assign_split_requires_both_date_and_target_inside(as_of, target, expected):
    frame = pd.DataFrame({"date": [pd.Timestamp(as_of)], "target_date": [pd.Timestamp(target)]})
    result = assign_split(frame).iloc[0]
    assert (pd.isna(result) if expected is None else result == expected)


# ----------------------------------------------------- trailing baseline input
@pytest.fixture
def random_panel():
    days = [d.strftime("%Y-%m-%d") for d in sessions_between(pd.Timestamp("2024-07-01"), pd.Timestamp("2024-07-31"))]
    rng = np.random.default_rng(0)
    frames = [
        pd.DataFrame(
            {
                "date": pd.to_datetime(days),
                "ticker": t,
                "adj_close": 100 * np.cumprod(1 + rng.normal(0, 0.02, len(days))),
                "bad_bar": False,
            }
        )
        for t in ["AAA", "BBB", "CCC"]
    ]
    return pd.concat(frames, ignore_index=True), days


def test_trailing_excess_matches_hand_computation(random_panel):
    prices, days = random_panel
    t, t5 = pd.Timestamp(days[10]), pd.Timestamp(days[5])
    close = prices.set_index(["ticker", "date"])["adj_close"]
    past = {k: close[(k, t)] / close[(k, t5)] - 1 for k in ["AAA", "BBB", "CCC"]}
    got = trailing_excess(prices, min_tickers=1).set_index(["ticker", "date"])["past5_excess"]
    assert got[("AAA", t)] == pytest.approx(past["AAA"] - np.mean(list(past.values())))
    assert got[("AAA", pd.Timestamp(days[4]))] != got[("AAA", pd.Timestamp(days[4]))]  # NaN: needs 5 prior rows


def test_trailing_excess_never_uses_data_after_t(random_panel):
    prices, days = random_panel
    cutoff = pd.Timestamp(days[12])
    before = trailing_excess(prices, min_tickers=1)
    changed = prices.copy()
    future = changed["date"] > cutoff
    changed.loc[future, "adj_close"] *= np.random.default_rng(1).uniform(0.5, 1.5, future.sum())
    after = trailing_excess(changed, min_tickers=1)
    keep = before["date"] <= cutoff
    pd.testing.assert_frame_equal(before[keep].reset_index(drop=True), after[keep].reset_index(drop=True))


def test_trailing_excess_is_invalid_when_the_window_touches_a_bad_bar(random_panel):
    prices, days = random_panel
    prices.loc[(prices["ticker"] == "AAA") & (prices["date"] == pd.Timestamp(days[8])), "bad_bar"] = True
    got = trailing_excess(prices, min_tickers=1).set_index(["ticker", "date"])["past5_excess"]
    assert np.isnan(got[("AAA", pd.Timestamp(days[10]))])  # window days[5..10] contains days[8]
    assert not np.isnan(got[("AAA", pd.Timestamp(days[14]))])  # window days[9..14] is clean


@pytest.mark.parametrize("bad_back", [0, 1, 2, 3, 4, 5], ids=lambda k: f"t-{k}")
def test_trailing_excess_bad_bar_anywhere_in_the_backward_window(random_panel, bad_back):
    prices, days = random_panel
    prices.loc[(prices["ticker"] == "AAA") & (prices["date"] == pd.Timestamp(days[10 - bad_back])), "bad_bar"] = True
    got = trailing_excess(prices, min_tickers=1).set_index(["ticker", "date"])["past5_excess"]
    assert np.isnan(got[("AAA", pd.Timestamp(days[10]))])


def test_trailing_excess_bad_bar_just_before_the_window_is_fine(random_panel):
    prices, days = random_panel
    prices.loc[(prices["ticker"] == "AAA") & (prices["date"] == pd.Timestamp(days[4])), "bad_bar"] = True
    got = trailing_excess(prices, min_tickers=1).set_index(["ticker", "date"])["past5_excess"]
    assert not np.isnan(got[("AAA", pd.Timestamp(days[10]))])  # window is days[5..10]


def test_trailing_excess_never_borrows_the_previous_tickers_tail(random_panel):
    prices, days = random_panel
    got = trailing_excess(prices, min_tickers=1)
    for ticker in ["BBB", "CCC"]:
        first = got[got["ticker"] == ticker].sort_values("date")["past5_excess"]
        assert first.iloc[:5].isna().all() and first.iloc[5:].notna().all()


def test_a_row_on_a_non_session_date_breaks_every_window_through_it(make_prices, sessions):
    dates = sessions[:3] + ["2024-07-04"] + sessions[3:]  # 07-04 was a holiday
    prices = pd.concat(
        [
            make_prices("AAA", dates, [100 + i for i in range(len(dates))]),
            make_prices("BBB", sessions, [50.0] * len(sessions)),
        ]
    )
    aaa = rows(labels_for(prices), "AAA")
    assert "2024-07-04" not in aaa.index
    assert "2024-07-01" not in aaa.index  # its 5th row ahead is only 4 sessions later


# ------------------------------------------------------------ feature guard
def test_feature_guard_accepts_trailing_columns():
    check_feature_columns(["ret", "past5_excess", "vol_20d"])


@pytest.mark.parametrize("column", sorted(FUTURE_COLUMNS | MEMBERSHIP_COLUMNS))
def test_feature_guard_rejects_future_and_membership_columns(column):
    with pytest.raises(ValueError, match="forbidden"):
        check_feature_columns(["ret", column])


def test_label_frame_future_columns_are_all_covered_by_the_guard(two_tickers):
    # Every column label_frame adds beyond the trailing ones must be in FUTURE_COLUMNS.
    frame = label_frame(two_tickers, min_tickers=1)
    added = set(frame.columns) - {"ticker", "date", "adj_close", "bad_bar", "session", "ret"}
    assert added <= FUTURE_COLUMNS


# ------------------------------------------------------------------ calendar
def test_sessions_between_clamps_to_the_calendar_end():
    last = get_calendar().last_session.tz_localize(None)
    got = sessions_between(last - pd.Timedelta(days=10), last + pd.Timedelta(days=60))
    assert got[-1] == last
