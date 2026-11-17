"""Safety and experimental-control tests for the bounded follow-up round."""

import json

import numpy as np
import pandas as pd
import pytest

from stocksight_data import research_round2 as r
from stocksight_data.features import model_features


def context_panel():
    days = pd.to_datetime(["2010-01-04", "2010-01-05", "2010-01-06"])
    return pd.DataFrame({
        "ticker": list("ABCD") * 3, "date": days.repeat(4),
        "ret_21d": [0., 1., 2., 6., 4., 2., 1., np.nan, -3., 1., 2., 8.],
    })


def test_exactly_four_new_configurations_and_no_settings_search():
    configs = r.configurations()
    assert len(configs) == 5 and len({c.name for c in configs}) == 5
    assert configs[0].name == r.BASE_NAME
    assert configs[1].features == r.SMALL_FEATURES and len(configs[1].features) == 12
    assert set(configs[1].features) <= set(model_features())
    assert [c.years for c in configs] == [None, None, 5, 10, None]
    assert configs[-1].features == (*model_features(), r.CONTEXT)
    assert r.BASE_SPEC.preprocess == "raw" and r.BASE_SPEC.family == "hgb"


def test_context_is_sample_skew_and_requires_enough_valid_stocks():
    frame = context_panel()
    result = r.market_context(frame, min_tickers=4)
    assert result.iloc[0] == pytest.approx(pd.Series([0., 1., 2., 6.]).skew(), rel=1e-6)
    assert result.iloc[:4].nunique() == 1
    assert result.iloc[4:8].isna().all()
    assert result.dtype == np.dtype("float32")


def test_context_never_uses_other_dates_or_future_labels():
    frame = context_panel()
    before = frame.copy(deep=True)
    first = r.market_context(frame, 3)
    frame.loc[frame.date == frame.date.max(), "ret_21d"] *= -1000
    frame["label"] = [0, 1] * 6
    after = r.market_context(frame, 3)
    pd.testing.assert_series_equal(first.iloc[:8], after.iloc[:8])
    # The feature takes no label-dependent filter; an unlabelled stock is still in the population.
    frame.loc[0, "label"] = np.nan
    assert r.market_context(frame, 3).iloc[0] == first.iloc[0]
    assert list(before.columns) == ["ticker", "date", "ret_21d"]


def test_context_sparse_and_constant_cross_sections_are_safe():
    frame = context_panel()
    assert r.market_context(frame, 150).isna().all()
    frame.ret_21d = 1.
    # Skew is undefined without variation; preserve missing rather than invent a signal.
    assert r.market_context(frame, 3).isna().all()
    with pytest.raises(ValueError, match="Duplicate"):
        r.market_context(pd.concat([frame, frame.iloc[:1]]), 3)


def test_feature_subset_cannot_silently_keep_excluded_rank_inputs():
    config = r.configurations()[1]
    fields = ["ticker", "date", "target_date", "label", "excess_ret", "past5_excess"]
    fields += [*model_features(), *(r.m.rank_name(c) for c in model_features())]
    frame = pd.DataFrame({c: [1.] for c in fields})
    selected = r.experiment_frame(frame, config)
    assert [c for c in selected if c in model_features()] == list(r.SMALL_FEATURES)
    assert "rk_ret_1d" not in selected and "ret_1d" not in selected


def test_recent_windows_keep_shared_evaluation_and_the_target_date_purge():
    days = pd.date_range("2000-01-03", "2018-12-31", freq="B")
    frame = pd.DataFrame({"date": days, "target_date": days + pd.offsets.BDay(5)})
    original = r.window_folds(frame, None)
    for years in (5, 10):
        recent = r.window_folds(frame, years)
        for base, fold in zip(original, recent):
            pd.testing.assert_index_equal(base["eval_index"], fold["eval_index"])
            fit = frame.loc[fold["train_index"]]
            ev = frame.loc[fold["eval_index"]]
            assert (fit.date > fold["fit_end"] - pd.DateOffset(years=years)).all()
            assert fit.target_date.max() <= fold["fit_end"] < ev.date.min()


def test_common_coverage_requires_the_same_context_and_baseline_observations():
    frame = pd.DataFrame({"past5_excess": [1., np.nan, 3., 4.], r.CONTEXT: [2., 2., np.nan, 2.]})
    fold = {"eval_index": frame.index}
    assert r.common_eval_index(frame, fold).tolist() == [0, 3]


def test_train_frame_cuts_at_the_reader_and_builds_context_before_labels(monkeypatch):
    reads = []
    hi = pd.Timestamp(r.SPLITS["train"][1])
    feats = context_panel()
    prices = pd.DataFrame({"ticker": list("ABCD"), "date": feats.date.iloc[:4],
                           "adj_close": [1., 2., 3., 4.], "bad_bar": False})
    labels = prices[["ticker", "date"]].assign(target_date=pd.Timestamp("2010-01-11"), label=1, excess_ret=0.1)

    def read(path, **kwargs):
        reads.append((path, kwargs))
        return feats.copy() if path == r.FEATURES_FILE else prices.copy()

    monkeypatch.setattr(r.pd, "read_parquet", read)
    monkeypatch.setattr(r, "build_labels", lambda p: labels)
    monkeypatch.setattr(r, "assign_split", lambda p: pd.Series("train", index=p.index))
    monkeypatch.setattr(r, "trailing_excess", lambda p: p[["ticker", "date"]].assign(past5_excess=.1))
    result = r.load_training_frame()
    assert r.CONTEXT in result and not any(c.startswith("rk_") for c in result)
    assert len(reads) == 2
    assert all(kwargs["filters"] == [("date", "<=", hi)] for _, kwargs in reads)


def test_explicit_raw_columns_match_the_original_rank_discovery_path():
    # The memory-saving path must leave the original raw HGB estimator unchanged.
    rng = np.random.default_rng(4)
    days = pd.date_range("2005-01-03", periods=60, freq="B")
    frame = pd.DataFrame({"date": days.repeat(4), "target_date": (days + pd.offsets.BDay(5)).repeat(4),
                          "label": np.tile([0, 1, 0, 1], 60), "x": rng.normal(size=240)})
    spec = r.m.ModelSpec("tiny", "hgb", "raw", (("min_samples_leaf", 5), ("max_iter", 4)), stride=1)
    original = r.m.fit_model(spec, frame.assign(rk_x=0.))
    explicit = r.m.fit_model(spec, frame, columns=["x"])
    np.testing.assert_array_equal(original.predict(frame), explicit.predict(frame))
    with pytest.raises(ValueError, match="forbidden"):
        r.m.fit_model(spec, frame, columns=["label"])


def test_changed_manifest_and_dataset_are_refused(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "ROOT", tmp_path)
    (tmp_path / "manifest.json").write_text(json.dumps({"dataset": "before"}))
    monkeypatch.setattr(r, "manifest_value", lambda: {"dataset": "after"})
    with pytest.raises(ValueError, match="inputs changed"):
        r.check_manifest()


def test_single_runner_lock_and_release_on_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "ROOT", tmp_path)
    with pytest.raises(LookupError):
        with r.run_lock():
            with pytest.raises(RuntimeError, match="Another run"):
                with r.run_lock():
                    pass
            raise LookupError("interrupted run")
    assert not (tmp_path / "run.lock").exists()


def test_experiments_cannot_bypass_baseline_reproduction(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="baseline folds"):
        r.require_reproduced_baseline()
    folder = tmp_path / r.BASE_NAME
    folder.mkdir()
    for i in range(6):
        (folder / f"fold-{i}.json").write_text(json.dumps({"reproduction": {"within_1e_6": True}}))
    r.require_reproduced_baseline()
    (folder / "fold-3.json").write_text(json.dumps({"reproduction": {"within_1e_6": False}}))
    with pytest.raises(RuntimeError, match="baseline folds"):
        r.require_reproduced_baseline()


def test_paired_brier_reports_direction_and_uncertainty():
    days = pd.date_range("2010-01-01", periods=40).repeat(2)
    y = np.tile([0, 1], 40)
    result = r.paired_brier_ci(days, y, y*.8+.1, np.full(len(y), .5))
    assert result["point"] == pytest.approx(-.24)
    np.testing.assert_allclose(result["ci95"], [-.24, -.24])
