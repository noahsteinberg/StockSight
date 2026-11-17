"""Small synthetic checks only. Never run the real-data confidence analysis."""

import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

SPEC = importlib.util.spec_from_file_location("confidence_analysis", Path(__file__).parents[1]/"scripts/analyze-confidence.py")
c = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(c)


@pytest.fixture
def predictions():
    frames = []
    for fold in range(3):
        dates = pd.date_range("2010-01-04", periods=60, freq="B")[fold*20:(fold+1)*20]
        frames.append(pd.DataFrame({
            "ticker": list("ABCD")*20, "date": dates.repeat(4), "fold": fold,
            "p": np.tile([.49, .51, .1, .9], 20), "label": np.tile([1, 0, 0, 1], 20),
            "past5_excess": np.tile([.1, -.1, .1, -.1], 20), "base_rate": .48,
        }))
    return pd.concat(frames, ignore_index=True)


def test_thresholds_ignore_current_future_predictions_and_all_outcomes(predictions):
    expected = c.thresholds(predictions, 1)
    changed = predictions.copy()
    changed.loc[changed.fold >= 1, "p"] = .5
    changed.label = 1-changed.label
    assert c.thresholds(changed, 1) == expected
    with pytest.raises(ValueError, match="earlier fold"):
        c.thresholds(predictions, 0)


def test_selective_improvement_is_compared_with_the_same_selected_baseline(predictions):
    result = c.evaluate(predictions, draws=30)
    assert result["evaluation_folds"] == [1, 2]
    assert len(result["policies"]) == 4
    full, selected = result["policies"][0], result["policies"][-1]
    assert full["model"]["accuracy"] == .5
    assert selected["model"]["accuracy"] == 1.
    assert selected["actual_coverage"] == .5  # tied scores: not a hidden exact top-10% filter
    assert selected["baselines_on_identical_rows"]["reversal_5d"]["accuracy"] == 1.
    assert selected["paired_uncertainty"]["accuracy_minus_reversal"]["point"] == 0.
    assert selected["paired_uncertainty"]["balanced_accuracy_minus_reversal"]["ci95"] == [0., 0.]
    assert not result["protocol"]["training"] and not result["protocol"]["test_scoring"]


def test_bootstrap_keeps_dates_where_the_model_answers_nothing(predictions):
    rows = predictions[predictions.fold == 1]
    mask = rows.date.to_numpy() == rows.date.iloc[0]
    stats = c.daily_stats(rows, mask)
    assert stats.shape == (20, 14)
    assert (stats[1:] == 0).all()
    assert stats[0, 0] == 4


def test_single_class_has_no_invented_balanced_accuracy():
    assert c.metrics([1, 1], [.8, .9])["balanced_accuracy"] is None
    assert c.metrics([], [])["accuracy"] is None


def test_zero_coverage_and_undefined_intervals_serialize_safely(predictions, tmp_path, monkeypatch):
    predictions.loc[predictions.fold == 0, "p"] = np.tile([0., 1., 0., 1.], 20)
    predictions.loc[predictions.fold > 0, "p"] = .5
    result = c.evaluate(predictions, draws=20)
    empty = result["policies"][-1]
    assert empty["rows"] == 0 and empty["model"]["accuracy"] is None
    ci = empty["paired_uncertainty"]["balanced_accuracy_minus_reversal"]
    assert ci["ci95"] is None and ci["undefined_draws"] == 20
    monkeypatch.setattr(c, "OUTPUT", tmp_path)
    c.write_outputs(result)
    json.loads((tmp_path/"results.json").read_text())
    assert "unavailable" in (tmp_path/"summary.md").read_text()


@pytest.mark.parametrize("kind", ["duplicate", "nan", "outside"])
def test_malformed_predictions_are_refused(predictions, kind):
    if kind == "duplicate":
        predictions = pd.concat([predictions, predictions.iloc[:1]])
    else:
        predictions.loc[0, "p"] = np.nan if kind == "nan" else 1.1
    with pytest.raises(ValueError):
        c.evaluate(predictions, draws=5)


def test_input_integrity_check_detects_tampered_prediction_file(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "ML", tmp_path)
    monkeypatch.setattr(c, "CACHE", tmp_path/"cache")
    monkeypatch.setattr(c, "CLEAN_FILE", tmp_path/"prices")
    c.CLEAN_FILE.write_bytes(b"frozen snapshot")
    (tmp_path/"reports").mkdir()
    (tmp_path/"reports/research_round2.json").write_text(json.dumps({"manifest": {
        "train_end": c.SPLITS["train"][1], "dataset_sha256": c.b.sha256_file(c.CLEAN_FILE),
    }}))
    folder = c.CACHE/c.MODEL
    folder.mkdir(parents=True)
    for i in range(6):
        data = folder/f"fold-{i}.parquet"
        data.write_bytes(b"saved predictions")
        (folder/f"fold-{i}.json").write_text(json.dumps({"reproduction": {"within_1e_6": True},
                                                       "predictions_sha256": c.b.sha256_file(data)}))
    c.verify_inputs()
    (folder/"fold-2.parquet").write_bytes(b"changed")
    with pytest.raises(ValueError, match="predictions changed"):
        c.verify_inputs()


def test_check_mode_never_runs_analysis(monkeypatch):
    monkeypatch.setattr(c.sys, "argv", ["analyze-confidence.py", "--check"])
    monkeypatch.setattr(c, "verify_inputs", lambda: {})
    monkeypatch.setattr(c, "load_predictions", lambda: pytest.fail("check mode launched analysis"))
    assert c.main() == 0
