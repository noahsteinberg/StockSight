"""Purged walk-forward folds inside the training split (contract 3.5)."""

from __future__ import annotations

import pandas as pd
import pytest

from stocksight_data.config import SPLITS
from stocksight_data.folds import DEFAULT_FOLD_ENDS, purged_walk_forward
from stocksight_data.trading_calendar import sessions_between


@pytest.fixture(scope="module")
def frame():
    days = sessions_between(pd.Timestamp("2000-01-03"), pd.Timestamp("2021-12-31"))
    pos = {d: i for i, d in enumerate(days)}
    rows = []
    for d in days:
        i = pos[d]
        if i + 5 < len(days):
            for t in ["AAA", "BBB"]:
                rows.append({"ticker": t, "date": d, "target_date": days[i + 5]})
    return pd.DataFrame(rows)


def test_folds_are_expanding_and_stay_inside_train(frame):
    folds = purged_walk_forward(frame)
    assert len(folds) == len(DEFAULT_FOLD_ENDS) - 1
    train_end = pd.Timestamp(SPLITS["train"][1])
    previous = 0
    for fold in folds:
        tr, ev = frame.loc[fold["train_index"]], frame.loc[fold["eval_index"]]
        assert len(tr) > previous  # expanding window
        previous = len(tr)
        assert ev["target_date"].max() <= train_end  # never touches validation
        assert tr["date"].min() >= pd.Timestamp(SPLITS["train"][0])


def test_no_label_window_is_shared_between_fit_and_eval_rows(frame):
    for fold in purged_walk_forward(frame):
        tr, ev = frame.loc[fold["train_index"]], frame.loc[fold["eval_index"]]
        assert tr["target_date"].max() <= fold["fit_end"] < ev["date"].min()
        assert ev["target_date"].max() <= fold["eval_end"]
        assert set(fold["train_index"]).isdisjoint(fold["eval_index"])


def test_purge_drops_the_last_five_sessions_before_each_boundary(frame):
    fold = purged_walk_forward(frame)[0]
    tr = frame.loc[fold["train_index"]]
    last_fit_as_of = tr["date"].max()
    boundary_sessions = sessions_between(last_fit_as_of, fold["fit_end"])
    assert len(boundary_sessions) == 6  # last fit as_of + 5 sessions = fit_end


def test_fold_ends_must_lie_inside_train(frame):
    with pytest.raises(ValueError, match="train"):
        purged_walk_forward(frame, fold_ends=["2010-12-31", "2019-06-28"])


def test_rows_without_a_target_date_are_rejected(frame):
    broken = frame.copy()
    broken.loc[broken.index[0], "target_date"] = pd.NaT
    with pytest.raises(ValueError, match="target_date"):
        purged_walk_forward(broken)
