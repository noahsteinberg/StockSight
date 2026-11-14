"""Baselines, metrics, block bootstrap and promotion gates (contract sections 4-5)."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from stocksight_data.baselines import (
    accuracy,
    balanced_accuracy,
    baseline_predictions,
    bootstrap_balanced_accuracy_diff,
    brier,
    build_eval_frame,
    check_gates,
    evaluate_split,
    freeze_gates,
    gate_model,
    load_frozen_gates,
    moving_block_indices,
    run_baselines,
)
from stocksight_data.config import CLEAN_FILE
from stocksight_data.trading_calendar import sessions_between


# ------------------------------------------------------------------- metrics
@pytest.mark.parametrize(
    "y,p,expected",
    [
        ([1, 1, 0, 0], [1, 1, 1, 1], 0.5),
        ([1, 1, 0, 0], [1, 0, 0, 0], 0.75),
        ([1, 0, 1, 0], [0.9, 0.1, 0.6, 0.4], 1.0),
    ],
    ids=["constant", "half-ones-all-zeros", "perfect"],
)
def test_balanced_accuracy(y, p, expected):
    assert balanced_accuracy(np.array(y), np.array(p)) == pytest.approx(expected)


def test_accuracy_and_brier():
    y, p = np.array([1, 0]), np.array([0.8, 0.4])
    assert accuracy(y, p) == pytest.approx(1.0)
    assert brier(y, p) == pytest.approx((0.2**2 + 0.4**2) / 2)


def test_threshold_half_counts_as_beat():
    assert accuracy(np.array([1]), np.array([0.5])) == 1.0


# ----------------------------------------------------------------- baselines
@pytest.mark.parametrize("majority", [0, 1])
def test_baseline_predictions(majority):
    preds = baseline_predictions(pd.Series([0.02, -0.01, 0.0]), majority_class=majority)
    assert list(preds["always_beat"]) == [float(majority)] * 3
    assert list(preds["momentum_5d"]) == [1.0, 0.0, 0.0]
    assert list(preds["reversal_5d"]) == [0.0, 1.0, 0.0]  # exactly zero: neither predicts a beat


# ----------------------------------------------------------------- bootstrap
def _panel(n_dates=60, n_tickers=20, seed=0):
    rng = np.random.default_rng(seed)
    dates = np.repeat(np.arange(n_dates), n_tickers)
    y = (rng.random(n_dates * n_tickers) > 0.5).astype(int)
    return dates, y


def test_moving_block_indices_are_contiguous_blocks():
    idx = moving_block_indices(n_dates=50, block=10, n_boot=30, rng=np.random.default_rng(0))
    assert idx.shape == (30, 50)
    assert idx.min() >= 0 and idx.max() <= 49
    blocks = idx.reshape(30, 5, 10)
    assert (np.diff(blocks, axis=2) == 1).all()  # each block is 10 consecutive dates


def test_block_as_long_as_the_series_returns_every_date_once():
    idx = moving_block_indices(n_dates=12, block=50, n_boot=5, rng=np.random.default_rng(0))
    assert (idx == np.arange(12)).all()


def test_bootstrap_of_identical_predictions_is_zero():
    dates, y = _panel()
    p = np.ones_like(y, dtype=float)
    assert bootstrap_balanced_accuracy_diff(dates, y, p, p, n_boot=200, seed=0) == pytest.approx((0.0, 0.0, 0.0))


def test_bootstrap_is_deterministic_for_a_seed():
    dates, y = _panel()
    noisy = np.where(np.random.default_rng(3).random(len(y)) < 0.6, y, 1 - y).astype(float)
    base = np.zeros_like(y, dtype=float)
    first = bootstrap_balanced_accuracy_diff(dates, y, noisy, base, n_boot=200, seed=7)
    assert first == bootstrap_balanced_accuracy_diff(dates, y, noisy, base, n_boot=200, seed=7)


def test_bootstrap_detects_a_clearly_better_model():
    dates, y = _panel()
    low, high, point = bootstrap_balanced_accuracy_diff(
        dates, y, y.astype(float), np.zeros_like(y, dtype=float), n_boot=200, seed=0
    )
    assert point == pytest.approx(0.5)
    assert 0 < low <= point <= high


def test_bootstrap_keeps_tickers_of_a_date_together():
    # All tickers on a date share one outcome: the date-clustered CI must be much
    # wider than one that treats the 1,200 rows as independent.
    n_dates, n_tickers = 60, 20
    rng = np.random.default_rng(5)
    day_y = (rng.random(n_dates) > 0.5).astype(int)
    day_p = np.where(rng.random(n_dates) < 0.6, day_y, 1 - day_y).astype(float)
    dates = np.repeat(np.arange(n_dates), n_tickers)
    y, p = np.repeat(day_y, n_tickers), np.repeat(day_p, n_tickers)
    base = np.zeros_like(p)
    low, high, _ = bootstrap_balanced_accuracy_diff(dates, y, p, base, n_boot=500, seed=0, block=1)
    low_r, high_r, _ = bootstrap_balanced_accuracy_diff(np.arange(len(y)), y, p, base, n_boot=500, seed=0, block=1)
    assert (high - low) > 3 * (high_r - low_r)


def test_block_bootstrap_widens_the_ci_for_autocorrelated_dates():
    # Outcomes persist in runs of 10 dates (like overlapping 5-day labels): blocks of
    # 10 must give a wider CI than resampling single dates.
    rng = np.random.default_rng(11)
    n_runs, run = 30, 10
    day_y = np.repeat((rng.random(n_runs) > 0.5).astype(int), run)
    day_p = np.repeat(np.where(rng.random(n_runs) < 0.65, day_y[::run], 1 - day_y[::run]), run).astype(float)
    dates, base = np.arange(len(day_y)), np.zeros(len(day_y))
    lo_b, hi_b, _ = bootstrap_balanced_accuracy_diff(dates, day_y, day_p, base, n_boot=1000, seed=0, block=10)
    lo_1, hi_1, _ = bootstrap_balanced_accuracy_diff(dates, day_y, day_p, base, n_boot=1000, seed=0, block=1)
    assert (hi_b - lo_b) > 1.5 * (hi_1 - lo_1)


def test_bootstrap_orders_dates_chronologically():
    # Rows arrive shuffled; blocks must still be built over sorted dates.
    dates, y = _panel(n_dates=40, n_tickers=5)
    p = np.where(np.random.default_rng(2).random(len(y)) < 0.7, y, 1 - y).astype(float)
    base = np.zeros_like(p)
    order = np.random.default_rng(4).permutation(len(y))
    a = bootstrap_balanced_accuracy_diff(dates, y, p, base, n_boot=300, seed=1)
    b = bootstrap_balanced_accuracy_diff(dates[order], y[order], p[order], base[order], n_boot=300, seed=1)
    assert a == pytest.approx(b)


# --------------------------------------------------------------------- gates
def test_bootstrap_raises_instead_of_dropping_undefined_draws():
    # One positive label on a single date: many block draws contain no positives.
    dates = np.arange(50)
    y = np.zeros(50, dtype=int)
    y[0] = 1
    p = np.zeros(50)
    with pytest.raises(ValueError, match="undefined"):
        bootstrap_balanced_accuracy_diff(dates, y, p, p, n_boot=200, seed=0, block=5)


def test_balanced_accuracy_is_nan_for_a_single_class():
    assert np.isnan(balanced_accuracy(np.array([1, 1]), np.array([1.0, 0.0])))


PASSING = dict(
    bal_acc=0.53,
    best_baseline="reversal_5d",
    best_baseline_bal_acc=0.52,
    ci_low=0.001,
    ci_vs="reversal_5d",
    acc=0.54,
    always_beat_acc=0.535,
    brier=0.248,
    constant_brier=0.249,
    yearly_bal_acc={2019: 0.51, 2020: 0.52, 2021: 0.505},
)


def test_check_gates_all_pass():
    gates = check_gates(**PASSING)
    assert gates["passed"] is True
    assert all(gates.values())


@pytest.mark.parametrize(
    "override,failed_gate",
    [
        ({"bal_acc": 0.52}, "beats_best_baseline"),
        ({"ci_low": -0.002}, "significant"),
        ({"acc": 0.53}, "accuracy_at_least_always_beat"),
        ({"brier": 0.25}, "better_than_constant_brier"),
        ({"yearly_bal_acc": {2019: 0.49, 2020: 0.53}}, "no_year_below_half"),
    ],
    ids=["bal-acc", "ci", "accuracy", "brier", "year-slice"],
)
def test_check_gates_each_gate_can_fail(override, failed_gate):
    gates = check_gates(**{**PASSING, **override})
    assert gates[failed_gate] is False
    assert gates["passed"] is False


def test_significance_against_a_weaker_baseline_does_not_count():
    gates = check_gates(**{**PASSING, "ci_vs": "always_beat", "ci_low": 0.02})
    assert gates["significant"] is False
    assert gates["passed"] is False


# ------------------------------------------------------------- gate_model
FROZEN = {
    "best_baseline": "reversal_5d",
    "majority_class": 0,
    "train_beat_rate": 0.5,
    "n_boot": 300,
    "seed": 0,
    "block": 5,
    "reference": {"rows": 6000},
}


@pytest.fixture
def reversal_world():
    """Validation-like rows where reversal_5d is right 60% of the time."""
    rng = np.random.default_rng(8)
    n_dates, n_tickers = 300, 20
    past = rng.normal(size=n_dates * n_tickers)
    reversal = (past < 0).astype(int)
    label = np.where(rng.random(len(past)) < 0.6, reversal, 1 - reversal)
    frame = pd.DataFrame(
        {
            "date": np.repeat(pd.bdate_range("2019-01-02", periods=n_dates), n_tickers),
            "label": pd.array(label, dtype="Int8"),
            "past5_excess": past,
        }
    )
    return frame, reversal


def test_gate_model_fails_a_model_that_beats_always_beat_but_not_the_best_baseline(reversal_world):
    frame, reversal = reversal_world
    noisy = np.where(np.random.default_rng(9).random(len(reversal)) < 0.8, reversal, 1 - reversal).astype(float)
    y = frame["label"].astype(int).to_numpy()
    low_vs_always, _, _ = bootstrap_balanced_accuracy_diff(frame["date"].to_numpy(), y, noisy, np.zeros(len(y)))
    assert low_vs_always > 0  # the old, mis-specified gate would have called this significant
    result = gate_model(frame, noisy, FROZEN)
    assert result["gates"]["significant"] is False
    assert result["gates"]["passed"] is False


def test_gate_model_passes_a_clearly_better_model(reversal_world):
    frame, _ = reversal_world
    perfect = frame["label"].astype(int).to_numpy().astype(float)
    result = gate_model(frame, perfect, FROZEN)
    assert result["gates"]["passed"] is True


def test_gate_model_scores_model_and_baselines_on_the_same_rows(reversal_world):
    frame, reversal = reversal_world
    p = reversal.astype(float)
    p[:1000] = np.nan  # e.g. a long-lookback feature that is still warming up
    result = gate_model(frame, p, FROZEN)
    kept = frame.iloc[1000:]
    assert result["rows"] == len(kept)
    assert result["coverage_of_frozen_rows"] == pytest.approx(len(kept) / 6000)
    y = kept["label"].astype(int)
    assert result["thresholds_on_these_rows"]["always_beat_acc"] == pytest.approx((y == 0).mean())


# ---------------------------------------------------------- frozen gates file
def test_frozen_gates_refuse_a_different_dataset(tmp_path):
    run = {
        "majority_class": 0,
        "train_beat_rate": 0.487,
        "splits": {
            "validation": {
                "best_naive_baseline": "reversal_5d",
                "rows": 100,
                "gate_thresholds_for_models": {
                    "best_baseline_bal_acc": 0.505,
                    "always_beat_acc": 0.508,
                    "constant_brier": 0.25,
                },
            }
        },
    }
    path = tmp_path / "gates_frozen.json"
    path.write_text(json.dumps(freeze_gates(run, "a" * 64, {"commit": None, "dirty": None})))
    assert load_frozen_gates(path, "a" * 64)["best_baseline"] == "reversal_5d"
    with pytest.raises(ValueError, match="not comparable"):
        load_frozen_gates(path, "b" * 64)


# ------------------------------------------------------- test split guard
@pytest.fixture
def three_period_prices():
    """3 tickers with 20 sessions in late 2018, 2019 and 2022 (one block per split)."""
    rng = np.random.default_rng(3)
    blocks = [("2018-11-26", "2018-12-31"), ("2019-03-01", "2019-03-29"), ("2022-03-01", "2022-03-29")]
    days = np.concatenate([sessions_between(pd.Timestamp(a), pd.Timestamp(b)) for a, b in blocks])
    frames = [
        pd.DataFrame(
            {"date": days, "ticker": t, "adj_close": 100 * np.cumprod(1 + rng.normal(0, 0.02, len(days))), "bad_bar": False}
        )
        for t in ["AAA", "BBB", "CCC"]
    ]
    return pd.concat(frames, ignore_index=True)


def test_run_baselines_leaves_the_test_split_out_by_default(three_period_prices):
    frame = build_eval_frame(three_period_prices, min_tickers=1)
    assert set(run_baselines(frame)["splits"]) == {"train", "validation"}
    with_test = run_baselines(frame, include_test=True)["splits"]
    assert "test" in with_test
    assert "gate_thresholds_for_models" not in with_test["test"]  # test never defines gates


# ---------------------------------------------------------------- evaluation
def test_evaluate_split_reports_baselines_and_thresholds():
    rng = np.random.default_rng(2)
    n_dates, n_tickers = 40, 10
    frame = pd.DataFrame(
        {
            "date": np.repeat(pd.bdate_range("2019-01-02", periods=n_dates), n_tickers),
            "ticker": np.tile([f"T{i}" for i in range(n_tickers)], n_dates),
            "past5_excess": rng.normal(size=n_dates * n_tickers),
            "label": (rng.random(n_dates * n_tickers) > 0.55).astype(int),
        }
    )
    result = evaluate_split(frame, train_beat_rate=0.47, majority_class=0)
    assert result["rows"] == 400 and result["dates"] == 40 and result["tickers"] == 10
    assert set(result["baselines"]) == {"always_beat", "momentum_5d", "reversal_5d", "constant_prob"}
    assert result["baselines"]["always_beat"]["accuracy"] == pytest.approx(1 - result["beat_rate"])
    t = result["gate_thresholds_for_models"]
    assert t["always_beat_acc"] == pytest.approx(1 - result["beat_rate"])
    assert t["constant_brier"] == pytest.approx(result["baselines"]["constant_prob"]["brier"])
    assert t["best_baseline_bal_acc"] == max(
        result["baselines"][b]["balanced_accuracy"] for b in ["always_beat", "momentum_5d", "reversal_5d"]
    )
    for diff in result["vs_always_beat_bal_acc"].values():
        assert diff["ci95"][0] <= diff["point"] <= diff["ci95"][1]


@pytest.mark.data
@pytest.mark.skipif(not CLEAN_FILE.exists(), reason="cleaned dataset not built")
def test_real_labels_look_forward_and_respect_the_purge():
    from stocksight_data.labels import assign_split, build_labels

    labels = build_labels(pd.read_parquet(CLEAN_FILE, columns=["ticker", "date", "adj_close", "bad_bar"]))
    labels["split"] = assign_split(labels)
    assert (labels["target_date"] > labels["date"]).all()
    train = labels[labels["split"] == "train"]
    assert train["target_date"].max() <= pd.Timestamp("2018-12-31")
    # Equal-weight mean benchmark: the excess return averages to zero on every date.
    assert labels.groupby("date")["excess_ret"].mean().abs().max() < 1e-12


@pytest.mark.data
@pytest.mark.skipif(not CLEAN_FILE.exists(), reason="cleaned dataset not built")
def test_frozen_gates_match_the_data_and_the_best_baseline_cannot_pass_itself():
    from stocksight_data.baselines import sha256_file
    from stocksight_data.config import GATES_FILE

    if not GATES_FILE.exists():
        pytest.skip("gates not frozen yet")
    gates = load_frozen_gates(GATES_FILE, sha256_file(CLEAN_FILE))  # raises if the data changed
    frame = build_eval_frame(pd.read_parquet(CLEAN_FILE, columns=["ticker", "date", "adj_close", "bad_bar"]))
    val = frame[(frame["split"] == "validation") & (frame["status"] == "labelled")].reset_index(drop=True)
    p = baseline_predictions(val["past5_excess"], gates["majority_class"])[gates["best_baseline"]]
    p[val["past5_excess"].isna().to_numpy()] = np.nan
    result = gate_model(val, p, gates)
    assert result["coverage_of_frozen_rows"] == pytest.approx(1.0)
    assert result["thresholds_on_these_rows"]["best_baseline_bal_acc"] == pytest.approx(gates["reference"]["best_baseline_bal_acc"])
    assert result["gates"]["beats_best_baseline"] is False and result["gates"]["passed"] is False
