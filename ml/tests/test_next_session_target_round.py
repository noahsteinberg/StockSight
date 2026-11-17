import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location("target_round", Path(__file__).parents[1] / "scripts/next-session-target-round.py")
r = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = r
SPEC.loader.exec_module(r)


def target_rows():
    return pd.DataFrame({"ticker": ["A", "B", "C", "A", "B", "C"],
                         "date": pd.to_datetime(["2010-01-04"] * 3 + ["2010-01-05"] * 3),
                         "target_date": pd.to_datetime(["2010-01-05"] * 3 + ["2010-01-06"] * 3),
                         "forward_return": [0.1, -0.2, 0.04, 0.2, 0.3, -0.1],
                         "previous_return": [0.01] * 6})


def test_market_is_equal_weight_and_reconstructs_absolute_return():
    rows = target_rows()
    market = r.market_targets(rows, minimum=3)
    np.testing.assert_allclose(market.market_return, [-0.02, 0.4 / 3])
    joined = rows.merge(market, on=["date", "target_date"])
    residual = joined.forward_return - joined.market_return
    np.testing.assert_allclose(residual + joined.market_return, joined.forward_return)
    np.testing.assert_allclose(residual.groupby(joined.date).mean(), 0, atol=1e-16)


def test_market_rejects_sparse_or_misaligned_universe():
    rows = target_rows()
    assert r.market_targets(rows, minimum=4).market_return.isna().all()
    rows.loc[0, "target_date"] += pd.Timedelta(days=1)
    with pytest.raises(ValueError, match="mismatched"):
        r.market_targets(rows, minimum=3)


def test_market_rejects_duplicate_stocks():
    with pytest.raises(ValueError, match="Duplicate"):
        r.market_targets(pd.concat([target_rows(), target_rows().iloc[:1]]))


def test_protected_period_is_rejected():
    rows = target_rows()
    r.assert_training_only(rows)
    rows.loc[0, "target_date"] = pd.Timestamp("2019-01-02")
    with pytest.raises(ValueError, match="Protected"):
        r.assert_training_only(rows)


def test_calibration_and_outer_folds_are_purged():
    dates = pd.bdate_range("2000-01-03", "2018-12-31")
    rows = pd.DataFrame({"date": dates[:-1], "target_date": dates[1:]})
    folds = r.helpers.purged_walk_forward(rows)
    assert len(folds) == 6
    for fold in folds:
        fit, calibration = r.helpers.fit_partition(rows.loc[fold["train_index"]], None)
        evaluation = rows.loc[fold["eval_index"]]
        assert calibration.date.nunique() == 252
        assert fit.target_date.max() < calibration.date.min()
        assert calibration.target_date.max() < evaluation.date.min()


def test_clipping_uses_fit_targets_and_leaves_outcomes_untouched():
    training = np.arange(1000, dtype=float)
    outcomes = np.array([-1e10, 1e10])
    clipped, bounds = r.clip_target(training)
    np.testing.assert_allclose(bounds, [4.995, 994.005])
    assert clipped.min() == bounds[0] and clipped.max() == bounds[1]
    np.testing.assert_array_equal(outcomes, [-1e10, 1e10])


def test_probability_mapping_only_learns_calibration_data():
    scores = np.array([-2., -1., 1., 2.])
    mapper = r.fit_mapper(scores, np.array([0, 0, 1, 1]))
    assert mapper[0].mean_[0] == 0
    mean_before = mapper[0].mean_.copy()
    p = mapper.predict_proba(np.array([[-1000.], [1000.]]))[:, 1]
    assert p[0] < 0.01 and p[1] > 0.99
    np.testing.assert_array_equal(mapper[0].mean_, mean_before)
    with pytest.raises(ValueError, match="both classes"):
        r.fit_mapper(scores, np.ones(4))


def scored_rows():
    rows = target_rows()
    rows["label"] = (rows.forward_return > 0).astype(int)
    rows["market_return"] = rows.groupby("date").forward_return.transform("mean")
    rows["market_previous"] = 0.0
    rows["excess_return"] = rows.forward_return - rows.market_return
    rows["rate"] = 0.6
    rows["relative_rate"] = 0.5
    rows["reference_p"] = 0.6
    for name in r.NAMES:
        rows[name] = rows.excess_return if name == r.NAMES[1] else rows.forward_return
        rows[f"p_{name}"] = np.where(rows[name] > 0, 0.8, 0.2)
    return rows


def test_direction_target_and_rank_are_not_conflated():
    rows = scored_rows()
    absolute = r.metrics(rows, r.NAMES[0])
    relative = r.metrics(rows, r.NAMES[1])
    assert absolute["accuracy"] == relative["accuracy"] == 1.0
    assert relative["direction_target"] == "relative"
    assert absolute["mean_daily_spearman_rank_ic"] == 1.0
    np.testing.assert_allclose(absolute["mean_daily_decile_spread"], 0.35)
    rows[r.NAMES[0]] = 0
    assert r.metrics(rows, r.NAMES[0])["mean_daily_spearman_rank_ic"] is None


def test_date_statistics_match_independent_row_metrics():
    rows = scored_rows()
    daily = r.daily_statistics(rows, r.NAMES[0])
    contrasts = r.contrasts(daily.sum(axis=0))
    np.testing.assert_allclose(contrasts["accuracy_minus_always_positive"], 1 - rows.label.mean())
    np.testing.assert_allclose(contrasts["brier_minus_fit_rate"], 0.04 - np.mean((rows.rate - rows.label)**2))
    np.testing.assert_allclose(contrasts["mean_daily_spearman_rank_ic"], 1)
    relative = r.contrasts(r.daily_statistics(rows, r.NAMES[1]).sum(axis=0), relative=True)
    assert "balanced_accuracy_minus_hgb_reference" not in relative


def test_block_bootstrap_is_reproducible_and_matches_point_estimate():
    daily = r.daily_statistics(scored_rows(), r.NAMES[0])
    result = r.uncertainty([daily], False, block=1, draws=50)
    assert result == r.uncertainty([daily], False, block=1, draws=50)
    assert result["mean_daily_spearman_rank_ic"]["point"] == 1
    np.testing.assert_allclose(result["mean_daily_spearman_rank_ic"]["ci95"], [1, 1])


def test_resume_rejects_tampered_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "OUTPUT", tmp_path)
    assert r.checkpoint(0) is None
    path = tmp_path / "fold-0.parquet"
    path.write_bytes(b"example")
    (tmp_path / "fold-0.json").write_text(json.dumps({"fold": 0, "sha256": r.b.sha256_file(path)}))
    assert r.checkpoint(0)["fold"] == 0
    path.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="changed"):
        r.checkpoint(0)


def test_frozen_protocol_change_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "OUTPUT", tmp_path)
    monkeypatch.setattr(r, "contract", lambda: {"version": 2})
    (tmp_path / "manifest.json").write_text(json.dumps({"version": 1}))
    with pytest.raises(ValueError, match="protocol changed"):
        r.verify()


@pytest.mark.parametrize("pilot", [True, False])
def test_complete_reporting_pipeline_without_training(tmp_path, monkeypatch, pilot):
    output, prior, ml = tmp_path / "output", tmp_path / "prior", tmp_path / "ml"
    for directory in (output, prior, ml / "docs", ml / "reports"):
        directory.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(r, "OUTPUT", output)
    monkeypatch.setattr(r, "ML", ml)
    monkeypatch.setattr(r.helpers, "PRIOR", prior)
    monkeypatch.setattr(r, "verify", lambda: None)
    (output / "manifest.json").write_text(json.dumps({"synthetic": True}))
    original_uncertainty = r.uncertainty
    monkeypatch.setattr(r, "uncertainty", lambda parts, relative, block: original_uncertainty(parts, relative, block, draws=20))
    for number in range(1 if pilot else 6):
        rows = scored_rows()
        rows["date"] += pd.DateOffset(years=number)
        rows["target_date"] += pd.DateOffset(years=number)
        path = output / f"fold-{number}.parquet"
        rows.to_parquet(path, index=False)
        (output / f"fold-{number}.json").write_text(json.dumps({"fold": number, "sha256": r.b.sha256_file(path)}))
        reference = rows[["ticker", "date", "target_date", "label"]].copy()
        reference["p"] = 0.6
        reference.to_parquet(prior / f"hgb-fold-{number}.parquet", index=False)
    r.report(pilot=pilot)
    result = json.loads((output / ("pilot.json" if pilot else "results.json")).read_text())
    assert result["completed_folds"] == (1 if pilot else 6)
    assert not result["validation_scored"] and not result["test_scored"] and not result["promotion"]
    assert (ml / "reports/next_session_target_round.json").exists() is not pilot
    assert len(result["results"]) == 3
    if not pilot:
        assert len(result["results"][r.NAMES[0]]["uncertainty"]) == 3


def test_full_report_refuses_incomplete_run(tmp_path, monkeypatch):
    monkeypatch.setattr(r, "OUTPUT", tmp_path)
    monkeypatch.setattr(r, "verify", lambda: None)
    with pytest.raises(ValueError, match="Missing fold 0"):
        r.report()
