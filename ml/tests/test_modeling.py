"""Modelling harness (contract 3.4-3.6, 5): point-in-time ranks, train-only fitting,
purged walk-forward selection, overlap subsampling, metrics and the validation guard."""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest
from sklearn.metrics import roc_auc_score

from stocksight_data import modeling as m
from stocksight_data.config import SPLITS
from stocksight_data.trading_calendar import sessions_between

FEATS = ["f_signal", "f_noise", "f_gappy"]


# ------------------------------------------------------------------ fixtures
def synthetic_frame(n_dates=80, n_tickers=40, seed=0, start="2010-01-04"):
    """Labelled-looking rows: f_signal predicts the label, f_gappy has missing values."""
    rng = np.random.default_rng(seed)
    days = sessions_between(pd.Timestamp(start), pd.Timestamp(start) + pd.Timedelta(days=int(n_dates * 1.6) + 20))
    days = days[: n_dates + 5]
    rows = []
    for i, d in enumerate(days[:n_dates]):
        signal = rng.normal(size=n_tickers)
        excess = 0.5 * signal + rng.normal(size=n_tickers)
        gappy = rng.normal(size=n_tickers)
        gappy[rng.random(n_tickers) < 0.2] = np.nan
        for k in range(n_tickers):
            rows.append(
                {
                    "ticker": f"T{k:02d}",
                    "date": d,
                    "target_date": days[i + 5],
                    "excess_ret": excess[k],
                    "label": int(excess[k] > 0),
                    "past5_excess": rng.normal(),
                    "f_signal": signal[k],
                    "f_noise": rng.normal(),
                    "f_gappy": gappy[k],
                }
            )
    frame = pd.DataFrame(rows)
    frame["label"] = frame["label"].astype("Int8")
    ranks = m.cross_sectional_rank(frame, FEATS)
    for c in FEATS:
        frame[m.rank_name(c)] = ranks[c]
    return frame


@pytest.fixture(scope="module")
def frame():
    return synthetic_frame()


def _prices_and_features(start="2018-10-01", end="2019-03-29", n_tickers=6, seed=1):
    rng = np.random.default_rng(seed)
    days = sessions_between(pd.Timestamp(start), pd.Timestamp(end))
    prices, feats = [], []
    for k in range(n_tickers):
        closes = 100 * np.cumprod(1 + rng.normal(0, 0.02, len(days)))
        prices.append(pd.DataFrame({"ticker": f"T{k}", "date": days, "adj_close": closes, "bad_bar": False}))
        feats.append(pd.DataFrame({"ticker": f"T{k}", "date": days, "f_signal": rng.normal(size=len(days)),
                                   "f_noise": rng.normal(size=len(days)), "f_gappy": rng.normal(size=len(days))}))
    return pd.concat(prices, ignore_index=True), pd.concat(feats, ignore_index=True)


# --------------------------------------------------------- cross-sectional ranks
def test_rank_is_centred_within_each_date_and_keeps_nan():
    df = pd.DataFrame({"date": ["d1"] * 4 + ["d2"] * 3, "x": [3.0, 1.0, np.nan, 2.0, 10.0, 30.0, 20.0]})
    r = m.cross_sectional_rank(df, ["x"])["x"]
    assert np.isnan(r.iloc[2])
    np.testing.assert_allclose(r.iloc[[1, 3, 0]], [-1 / 3, 0.0, 1 / 3])  # 3 valid values on d1
    np.testing.assert_allclose(r.iloc[4:], [-1 / 3, 1 / 3, 0.0])
    assert r.abs().max() < 0.5


def test_rank_ignores_other_dates_and_monotone_rescaling():
    df = pd.DataFrame({"date": ["d1"] * 3 + ["d2"] * 3, "x": [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]})
    base = m.cross_sectional_rank(df, ["x"])["x"]
    df2 = df.assign(x=np.where(df["date"] == "d2", df["x"] * 1000, np.exp(df["x"])))
    pd.testing.assert_series_equal(base, m.cross_sectional_rank(df2, ["x"])["x"])


# ------------------------------------------------------------- frame building
def test_selection_frame_is_train_only_and_ignores_prices_after_train_end():
    prices, feats = _prices_and_features()
    a = m.build_frame(prices, feats, "train", FEATS, min_tickers=2)
    train_end = pd.Timestamp(SPLITS["train"][1])
    assert len(a) > 0 and a["date"].max() <= train_end and a["target_date"].max() <= train_end
    shocked = prices.copy()
    after = shocked["date"] > train_end
    shocked.loc[after, "adj_close"] *= np.linspace(0.1, 10, after.sum())
    feats_shocked = feats.copy()
    feats_shocked.loc[feats_shocked["date"] > train_end, FEATS] = 999.0
    b = m.build_frame(shocked, feats_shocked, "train", FEATS, min_tickers=2)
    pd.testing.assert_frame_equal(a, b)


def test_validation_frame_never_reads_prices_after_validation_end():
    prices, feats = _prices_and_features(start="2021-09-01", end="2022-03-31")
    a = m.build_frame(prices, feats, "validation", FEATS, min_tickers=2)
    val_end = pd.Timestamp(SPLITS["validation"][1])
    assert len(a) > 0 and a["target_date"].max() <= val_end
    shocked = prices.copy()
    shocked.loc[shocked["date"] > val_end, "adj_close"] = 1.0
    pd.testing.assert_frame_equal(a, m.build_frame(shocked, feats, "validation", FEATS, min_tickers=2))


@pytest.mark.parametrize("split", ["train", "validation"])
def test_label_code_never_receives_prices_after_the_split_end(monkeypatch, split):
    """Outputs alone cannot show this (the purge already makes train labels independent of later
    prices), so spy on the inputs: later outcomes are never even computed."""
    prices, feats = _prices_and_features(start="2018-10-01", end="2022-02-28")
    seen = []
    for fn in ("build_labels", "trailing_excess"):
        real = getattr(m, fn)
        monkeypatch.setattr(m, fn, lambda p, *a, _real=real, **k: (seen.append(p["date"].max()), _real(p, *a, **k))[1])
    m.build_frame(prices, feats, split, FEATS, min_tickers=2)
    assert len(seen) == 2 and max(seen) <= pd.Timestamp(SPLITS[split][1])


def test_test_split_is_refused():
    prices, feats = _prices_and_features()
    with pytest.raises(ValueError, match="test"):
        m.build_frame(prices, feats, "test", FEATS, min_tickers=2)


def test_forward_looking_feature_columns_are_refused():
    prices, feats = _prices_and_features()
    with pytest.raises(ValueError, match="forbidden"):
        m.build_frame(prices, feats.assign(excess_ret=0.0), "train", FEATS + ["excess_ret"], min_tickers=2)


def test_ranks_use_every_ticker_on_the_date_not_only_labelled_rows():
    """A row without a label (its forward window is invalid) still counts in the rank population:
    excluding it would select the population on future information."""
    prices, feats = _prices_and_features()
    d = pd.Timestamp("2018-11-01")
    nxt = sessions_between(d, d + pd.Timedelta(days=10))[3]
    prices.loc[(prices["ticker"] == "T0") & (prices["date"] == nxt), ["adj_close", "bad_bar"]] = [np.nan, True]
    feats.loc[feats["date"] == d, "f_signal"] = [5.0, 0.0, 1.0, 2.0, 3.0, 4.0]  # T0 is the largest
    out = m.build_frame(prices, feats, "train", FEATS, min_tickers=2)
    on_d = out[out["date"] == d].set_index("ticker")
    assert "T0" not in on_d.index  # no valid label for T0 on d
    # T5 is 2nd of 6 (rank 5 -> (5-0.5)/6-0.5 = 1/4), not 1st of 5 (would be 0.4)
    np.testing.assert_allclose(on_d.loc["T5", m.rank_name("f_signal")], 0.25)


def test_frame_carries_reversal_input_and_labels():
    prices, feats = _prices_and_features()
    out = m.build_frame(prices, feats, "train", FEATS, min_tickers=2)
    assert {"label", "excess_ret", "past5_excess", "target_date"} <= set(out.columns)
    assert out["label"].notna().all()


# ------------------------------------------------------------- subsampling
def test_stride_mask_keeps_every_kth_date_with_all_its_tickers():
    dates = pd.Series(pd.to_datetime(["2020-01-02", "2020-01-03", "2020-01-06", "2020-01-07"]).repeat(3))
    keep = m.stride_mask(dates, stride=2, offset=0)
    assert keep.sum() == 6
    assert set(dates[keep]) == set(pd.to_datetime(["2020-01-02", "2020-01-06"]))
    assert set(dates[m.stride_mask(dates, stride=2, offset=1)]) == set(pd.to_datetime(["2020-01-03", "2020-01-07"]))
    with pytest.raises(ValueError):
        m.stride_mask(dates, stride=2, offset=2)


# ----------------------------------------------------------- preprocessing
def test_rank_preprocessor_fills_with_median_rank_and_adds_fit_time_indicators(frame):
    pre = m.Preprocessor("rank", FEATS).fit(frame.iloc[:400])
    assert pre.indicators == ["f_gappy"]
    x = pre.transform(frame)
    assert x.shape == (len(frame), len(FEATS) + 1)
    assert not np.isnan(x).any()
    gap = frame["f_gappy"].isna().to_numpy()
    np.testing.assert_array_equal(x[gap, 2], 0.0)
    np.testing.assert_array_equal(x[:, 3], gap.astype(float))


def test_indicator_set_is_frozen_at_fit_time(frame):
    pre = m.Preprocessor("rank", FEATS).fit(frame.dropna(subset=["f_gappy"]))
    assert pre.indicators == []
    assert pre.transform(frame).shape[1] == len(FEATS)


def test_winsor_preprocessor_learns_bounds_from_fit_rows_only(frame):
    fit, ev = frame.iloc[:1600], frame.iloc[1600:].copy()
    pre = m.Preprocessor("winsor", FEATS).fit(fit)
    ev.loc[ev.index[0], "f_signal"] = 1e6
    x = pre.transform(ev)
    lo, hi = np.nanpercentile(fit["f_signal"], [1, 99])
    np.testing.assert_allclose(x[0, 0], (hi - pre.mean_[0]) / pre.std_[0], rtol=1e-5)
    contaminated = m.Preprocessor("winsor", FEATS).fit(pd.concat([fit, ev]))
    assert not np.allclose(contaminated.transform(fit), pre.transform(fit))


def test_raw_preprocessor_keeps_nan_for_native_handling(frame):
    x = m.Preprocessor("raw", FEATS).fit(frame).transform(frame)
    assert np.isnan(x[:, 2]).sum() == frame["f_gappy"].isna().sum()


# ----------------------------------------------------- market-state experiment
def _with_market(frame):
    level = frame.groupby("date")["f_signal"].transform("mean")  # one value per date
    return frame.assign(mkt_vol_21d=level.astype("float32") * 10 + 3)


def test_market_columns_are_standardised_on_fit_rows_not_ranked(frame):
    df = _with_market(frame)
    pre = m.Preprocessor("rank", FEATS, market_columns=["mkt_vol_21d"]).fit(df.iloc[:1600])
    x = pre.transform(df)
    assert x.shape[1] == len(FEATS) + 1 + 1  # 3 ranks, 1 market, 1 indicator (f_gappy)
    mk = x[:, len(FEATS)]
    assert np.unique(mk).size > 1  # a per-date rank would be a constant 0
    raw = df["mkt_vol_21d"].iloc[:1600]
    np.testing.assert_allclose(mk[:1600].mean(), ((raw.clip(*np.percentile(raw, [1, 99])) - pre.market.mean_[0])
                                                  / pre.market.std_[0]).mean(), atol=1e-5)


def test_default_specs_ignore_market_columns_even_if_present(frame):
    df = _with_market(frame)
    plain = m.fit_model(m.ModelSpec("lr", "lr", "rank", (("C", 1.0),), stride=1), df)
    assert plain.members[0][0].market is None
    with_mkt = m.fit_model(m.ModelSpec("lr_m", "lr", "rank", (("C", 1.0),), stride=1, market=True), df)
    assert with_mkt.members[0][0].market.columns == ["mkt_vol_21d"]


def test_market_flag_changes_config_id_and_default_id_is_unchanged():
    base = m.ModelSpec("x", "lr", "rank", (("C", 1.0),))
    assert base.config_id() != m.ModelSpec("x", "lr", "rank", (("C", 1.0),), market=True).config_id()
    key = json.dumps(["lr", "rank", [("C", 1.0)], m.STRIDE, 1], default=str)
    import hashlib
    assert base.config_id() == hashlib.sha256(key.encode()).hexdigest()[:12]


def test_build_frame_keeps_market_columns_raw():
    prices, feats = _prices_and_features()
    feats = feats.assign(mkt_vol_21d=feats.groupby("date")["f_signal"].transform("mean"))
    out = m.build_frame(prices, feats, "train", FEATS, min_tickers=2, market_columns=["mkt_vol_21d"])
    assert "mkt_vol_21d" in out and m.rank_name("mkt_vol_21d") not in out
    assert out.groupby("date")["mkt_vol_21d"].nunique().max() == 1


# ------------------------------------------------------------------ metrics
def test_per_date_auc_matches_sklearn_and_skips_one_class_dates():
    rng = np.random.default_rng(3)
    y = rng.integers(0, 2, 200)
    p = rng.random(200) + 0.3 * y
    dates = np.repeat(["a", "b"], 100)
    expected = np.mean([roc_auc_score(y[:100], p[:100]), roc_auc_score(y[100:], p[100:])])
    assert m.per_date_auc(dates, y, p) == pytest.approx(expected)
    dates3 = np.concatenate([dates, ["c"] * 5])
    y3, p3 = np.concatenate([y, np.ones(5, int)]), np.concatenate([p, rng.random(5)])
    assert m.per_date_auc(dates3, y3, p3) == pytest.approx(expected)


def test_per_date_rank_ic_is_one_for_monotone_predictions():
    dates = np.repeat(["a", "b"], 50)
    excess = np.random.default_rng(0).normal(size=100)
    assert m.per_date_rank_ic(dates, np.exp(excess), excess) == pytest.approx(1.0)
    assert m.per_date_rank_ic(dates, -excess, excess) == pytest.approx(-1.0)


def test_score_reports_gate_metrics_and_reversal_on_the_same_rows(frame):
    p = np.where(frame["past5_excess"] < 0, 0.6, 0.4)  # exactly the reversal rule
    s = m.score(frame, p, base_rate=0.5)
    assert s["bal_acc"] == pytest.approx(s["reversal_bal_acc"])
    assert s["bal_acc_minus_reversal"] == pytest.approx(0.0)
    assert set(s) >= {"accuracy", "brier", "log_loss", "auc_date", "ic_date", "constant_brier", "pred_beat_share"}
    assert s["constant_brier"] == pytest.approx(0.25)


# ------------------------------------------------------------- walk-forward
def _two_folds(frame):
    days = np.sort(frame["date"].unique())
    ends = [days[20], days[45], days[74]]
    folds = []
    for i in range(2):
        fit = frame["target_date"] <= ends[i]
        ev = (frame["date"] > ends[i]) & (frame["target_date"] <= ends[i + 1])
        folds.append({"fold": i, "fit_end": ends[i], "eval_end": ends[i + 1],
                      "train_index": frame.index[fit], "eval_index": frame.index[ev]})
    return folds


def test_walk_forward_fits_only_on_past_rows_of_the_fold(frame, monkeypatch):
    seen_fit = []
    real_fit = m.fit_model

    def spy(spec, rows, seed=0):
        seen_fit.append(rows)
        return real_fit(spec, rows, seed)

    monkeypatch.setattr(m, "fit_model", spy)
    spec = m.ModelSpec("lr_test", "lr", "rank", (("C", 1.0),), stride=5)
    folds = _two_folds(frame)
    oof, diag = m.walk_forward(frame, spec, folds)
    for fold, rows in zip(folds, seen_fit):
        assert rows["target_date"].max() <= fold["fit_end"]
        assert set(rows.index) == set(fold["train_index"])
    assert set(oof.index) == set(folds[0]["eval_index"]) | set(folds[1]["eval_index"])
    assert oof["p"].between(0, 1).all()
    assert len(diag) == 2 and {"fold", "fit_rows", "fit_dates", "fit_bal_acc"} <= set(diag[0])


def test_fit_uses_every_stride_th_date(frame, monkeypatch):
    seen = []

    class Spy:
        def __init__(self, **kw):
            pass

        def fit(self, X, y, **kw):
            seen.append(len(y))
            return self

    monkeypatch.setitem(m.ESTIMATORS, "lr", Spy)
    m.fit_model(m.ModelSpec("lr_test", "lr", "rank", (), stride=5), frame)
    n_dates = frame["date"].nunique()
    assert seen == [(-(-n_dates // 5)) * frame["ticker"].nunique()]


def test_walk_forward_learns_a_planted_signal(frame):
    spec = m.ModelSpec("lr_test", "lr", "rank", (("C", 1.0),), stride=1)
    oof, _ = m.walk_forward(frame, spec, _two_folds(frame))
    s = m.score(frame.loc[oof.index], oof["p"].to_numpy(), base_rate=0.5)
    assert s["auc_date"] > 0.6 and s["bal_acc"] > 0.55


@pytest.mark.parametrize("family,pre,params", [
    ("hgb", "raw", (("learning_rate", 0.1), ("max_leaf_nodes", 4), ("min_samples_leaf", 20), ("max_iter", 30))),
    ("rf", "rank", (("n_estimators", 20), ("max_depth", 3), ("min_samples_leaf", 20))),
])
def test_tree_families_fit_and_predict(frame, family, pre, params):
    spec = m.ModelSpec(f"{family}_test", family, pre, params, stride=1)
    model = m.fit_model(spec, frame.iloc[:2400])
    p = model.predict(frame.iloc[2400:])
    assert p.shape == (len(frame) - 2400,) and np.all((p > 0) & (p < 1))


def test_hgb_early_stopping_holdout_is_later_and_purged(frame):
    fit_rows, holdout = m.temporal_holdout(frame, sessions=20)
    assert fit_rows["target_date"].max() < holdout["date"].min()
    assert holdout["date"].nunique() == 20
    assert holdout["date"].min() > fit_rows["date"].max()
    assert len(fit_rows) + len(holdout) < len(frame)  # the purge drops rows in between


def test_bagging_averages_one_model_per_offset(frame):
    spec = m.ModelSpec("lr_bag", "lr", "rank", (("C", 1.0),), stride=5, bags=5)
    model = m.fit_model(spec, frame)
    assert len(model.members) == 5
    p = model.predict(frame)
    singles = np.mean([pre_est[1].predict_proba(pre_est[0].transform(frame))[:, 1] for pre_est in model.members], axis=0)
    np.testing.assert_allclose(p, singles)


def test_model_spec_has_a_stable_config_id():
    a = m.ModelSpec("x", "lr", "rank", (("C", 1.0),))
    b = m.ModelSpec("x", "lr", "rank", (("C", 1.0),))
    assert a.config_id() == b.config_id()
    assert a.config_id() != m.ModelSpec("x", "lr", "rank", (("C", 0.1),)).config_id()


def test_unknown_family_or_preprocessing_is_rejected():
    with pytest.raises(ValueError):
        m.ModelSpec("x", "svm", "rank", ())
    with pytest.raises(ValueError):
        m.ModelSpec("x", "lr", "zscore", ())


def test_candidate_grid_names_are_unique_and_valid():
    names = [s.name for s in m.candidate_specs()]
    assert len(names) == len(set(names))
    assert {s.family for s in m.candidate_specs()} == {"lr", "hgb", "rf"}


# --------------------------------------------------------------- calibration
def test_nested_platt_uses_only_earlier_folds():
    rng = np.random.default_rng(0)
    oof = pd.DataFrame({"fold": np.repeat([0, 1, 2], 300), "p": rng.uniform(0.3, 0.7, 900)})
    y = (rng.random(900) < oof["p"]).astype(int).to_numpy()
    cal = m.nested_platt(oof, y)
    assert cal[oof["fold"] == 0].isna().all()
    y2 = y.copy()
    y2[(oof["fold"] == 2).to_numpy()] = 1 - y2[(oof["fold"] == 2).to_numpy()]  # same-fold outcomes change
    cal2 = m.nested_platt(oof, y2)
    np.testing.assert_allclose(cal[oof["fold"] == 1], cal2[oof["fold"] == 1])
    np.testing.assert_allclose(cal[oof["fold"] == 2], cal2[oof["fold"] == 2])


def test_platt_recovers_a_shift():
    rng = np.random.default_rng(1)
    p = rng.uniform(0.4, 0.6, 20000)
    y = (rng.random(20000) < p - 0.05).astype(int)
    f = m.platt_fit(p, y)
    assert abs(f(np.array([0.5]))[0] - 0.45) < 0.02


# ----------------------------------------------------------- selection
def _s(family, bal, gate=3, n=6, rev=0.002, acc=0.512, maj=0.511, brier_ok=True):
    return {"family": family, "mean_bal_acc": bal, "folds_passing_gate_proxies": gate, "n_folds": n,
            "mean_bal_acc_minus_reversal": rev, "mean_accuracy": acc, "mean_majority_acc": maj,
            "brier_beats_constant": brier_ok}


def test_choose_finalists_requires_mean_gate_analogues_and_ranks_by_gate_proxy_folds():
    summary = {
        "lr_a": _s("lr", 0.51, gate=2),
        "lr_b": _s("lr", 0.52, gate=1),  # higher bal acc, but passes the proxies in fewer folds
        "hgb_a": _s("hgb", 0.515, gate=3),
        "hgb_b": _s("hgb", 0.53, rev=-0.001),  # does not beat reversal on average
        "rf_a": _s("rf", 0.505, gate=4),
        "rf_b": _s("rf", 0.53, brier_ok=False),
        "rf_c": _s("rf", 0.53, gate=5, acc=0.509),  # would win, but accuracy is below majority
    }
    assert m.choose_finalists(summary, max_n=3) == ["rf_a", "hgb_a", "lr_a"]
    assert m.choose_finalists(summary, max_n=2) == ["rf_a", "hgb_a"]


def test_choose_finalists_compares_gate_proxy_counts_as_shares_of_folds():
    summary = {"a": _s("rf", 0.51, gate=3, n=5), "b": _s("hgb", 0.52, gate=3, n=6)}
    assert m.choose_finalists(summary) == ["a", "b"]  # 3/5 > 3/6


def test_choose_finalists_can_return_none():
    assert m.choose_finalists({"x": _s("lr", 0.52, brier_ok=False)}) == []


def test_summarise_folds():
    good = {"bal_acc": 0.51, "brier": 0.249, "constant_brier": 0.25, "auc_date": 0.52, "ic_date": 0.02,
            "bal_acc_minus_reversal": 0.0, "accuracy": 0.51, "majority_acc": 0.505, "log_loss": 0.69}
    bad = {"bal_acc": 0.48, "brier": 0.251, "constant_brier": 0.25, "auc_date": 0.49, "ic_date": -0.01,
           "bal_acc_minus_reversal": -0.02, "accuracy": 0.49, "majority_acc": 0.505, "log_loss": 0.70}
    s = m.summarise([good, good, bad], family="lr")
    assert s["mean_bal_acc"] == pytest.approx(0.5)
    assert s["worst_bal_acc"] == pytest.approx(0.48)
    assert s["folds_beating_reversal"] == 0
    assert s["brier_beats_constant"] is True  # mean 0.24967 < 0.25
    assert s["folds_passing_gate_proxies"] == 0  # "good" ties reversal, which is not a pass
    passing = {**good, "bal_acc_minus_reversal": 0.001}
    assert m.summarise([passing, good, bad], family="lr")["folds_passing_gate_proxies"] == 1
    assert m.summarise([{**passing, "accuracy": 0.50}], family="lr")["folds_passing_gate_proxies"] == 0


def test_score_majority_accuracy_uses_the_fit_majority_class(frame):
    s = m.score(frame, np.full(len(frame), 0.4), base_rate=0.45)
    assert s["majority_acc"] == pytest.approx(1 - frame["label"].mean())
    assert m.score(frame, np.full(len(frame), 0.4), base_rate=0.55)["majority_acc"] == pytest.approx(frame["label"].mean())


# --------------------------------------------------------- validation guard
def test_validation_access_is_logged_and_repeats_need_a_reason(tmp_path):
    log = tmp_path / "validation_access_log.jsonl"
    specs = [m.ModelSpec("a", "lr", "rank", (("C", 1.0),)), m.ModelSpec("b", "hgb", "raw", ())]
    assert m.record_validation_access(log, specs, reason=None) == 1
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["n_finalists"] == 2 and entry["config_ids"] == [s.config_id() for s in specs]
    with pytest.raises(PermissionError, match="already judged"):
        m.record_validation_access(log, specs[:1], reason=None)
    assert m.record_validation_access(log, specs[:1], reason="fixed a preprocessing bug") == 2
    assert json.loads(log.read_text().splitlines()[1])["reason"] == "fixed a preprocessing bug"


def test_cumulative_validation_trials_are_capped(tmp_path):
    log = tmp_path / "log.jsonl"
    first = [m.ModelSpec("a", "lr", "rank", (("C", 1.0),)), m.ModelSpec("b", "lr", "rank", (("C", 2.0),))]
    later = [m.ModelSpec("c", "lr", "rank", (("C", 3.0),)), m.ModelSpec("d", "lr", "rank", (("C", 4.0),))]
    m.record_validation_access(log, first, reason=None)
    with pytest.raises(PermissionError, match="cumulative"):
        m.record_validation_access(log, later, reason=None)  # 4 distinct candidates > MAX_FINALISTS
    assert m.record_validation_access(log, later, reason="team agreed to a second round") == 2


def test_a_member_judged_inside_one_candidate_counts_for_another(tmp_path):
    log = tmp_path / "log.jsonl"
    rf = m.ModelSpec("rf", "rf", "rank", (("max_depth", 3),))
    calibrated = m.ModelSpec("rf+platt", "rf", "rank", (("candidate", rf.config_id() + "+platt"),))
    m.record_validation_access(log, [calibrated], reason=None, members=[[rf.config_id()]])
    with pytest.raises(PermissionError, match="already judged"):
        m.record_validation_access(log, [rf], reason=None)
    other = tmp_path / "other.jsonl"  # the other order: plain model first, then a candidate built on it
    m.record_validation_access(other, [rf], reason=None)
    with pytest.raises(PermissionError, match="already judged"):
        m.record_validation_access(other, [calibrated], reason=None, members=[[rf.config_id()]])


def test_completed_marker_is_not_an_access(tmp_path):
    log = tmp_path / "log.jsonl"
    n = m.record_validation_access(log, [m.ModelSpec("a", "lr", "rank", ())], reason=None)
    m.mark_validation_completed(log, n)
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    assert [e["status"] for e in entries] == ["started", "completed"]
    assert m.record_validation_access(log, [m.ModelSpec("b", "lr", "rank", (("C", 2.0),))], reason=None) == 2


def test_judge_names_must_be_recomputed_finalists_unless_a_reason_is_given():
    summary = {"a": _s("rf", 0.51), "b": _s("hgb", 0.52, brier_ok=False)}
    assert m.check_judge_names(["a"], summary, reason=None) == ["a"]
    with pytest.raises(PermissionError, match="not finalists"):
        m.check_judge_names(["b"], summary, reason=None)
    assert m.check_judge_names(["b"], summary, reason="reference model for the report") == ["b"]


def test_common_fold_summary_drops_fold_zero():
    folds = [{"fold": k, "bal_acc": 0.5 + k / 100, "brier": 0.249, "constant_brier": 0.25, "auc_date": 0.5,
              "ic_date": 0.0, "bal_acc_minus_reversal": 0.001, "accuracy": 0.51, "majority_acc": 0.5,
              "log_loss": 0.69} for k in range(6)]
    s = m.common_summary(folds, family="lr")
    assert s["n_folds"] == 5 and s["mean_bal_acc"] == pytest.approx(0.53)


def test_fit_base_rate_uses_all_strided_rows_including_the_hgb_holdout(frame):
    spec = m.ModelSpec("h", "hgb", "raw", (("max_iter", 5),), stride=5)
    rows = frame.iloc[:2000]
    expected = rows.loc[m.stride_mask(rows["date"], 5, 0), "label"].mean()
    assert m.fit_base_rate(rows, spec) == pytest.approx(expected)
    _, diag = m.walk_forward(frame, spec, _two_folds(frame)[:1])
    fold_rows = frame.loc[_two_folds(frame)[0]["train_index"]]
    assert diag[0]["fit_beat_rate"] == pytest.approx(m.fit_base_rate(fold_rows, spec))


def test_too_many_finalists_are_refused(tmp_path):
    specs = [m.ModelSpec(f"s{i}", "lr", "rank", (("C", float(i + 1)),)) for i in range(m.MAX_FINALISTS + 1)]
    with pytest.raises(ValueError, match="finalists"):
        m.record_validation_access(tmp_path / "log.jsonl", specs, reason=None)
