"""Cross-check the saved diagnostic; training folds only, no model fitting.

Run after analyze-confidence.py. Fixed block lengths are sensitivity checks,
not candidate selection. Outputs remain in ignored data/confidence-analysis.
"""

import importlib.util
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss
from threadpoolctl import threadpool_limits

spec = importlib.util.spec_from_file_location("confidence", Path(__file__).with_name("analyze-confidence.py"))
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def main():
    c.verify_inputs()
    saved = json.loads((c.OUTPUT / "results.json").read_text())
    predictions = c.load_predictions()
    checks, sensitivity = [], []
    for policy in saved["policies"]:
        coverage = policy["requested_coverage"]
        stats, parts, folds = [], [], []
        for fold in saved["evaluation_folds"]:
            rows = predictions[predictions.fold == fold]
            keep = np.abs(rows.p.to_numpy() - .5) >= c.thresholds(predictions, fold)[coverage]
            selected = rows.loc[keep]
            parts.append(selected)
            stats.append(c.daily_stats(rows, keep))
            y, call = selected.label, selected.p >= .5
            rev = selected.past5_excess < 0
            folds.append({"fold": fold, "rows": len(selected), "coverage": float(keep.mean()),
                          "model_ba": balanced_accuracy_score(y, call),
                          "reversal_ba": balanced_accuracy_score(y, rev)})
        chosen = c.pd.concat(parts)
        y, call = chosen.label, chosen.p >= .5
        independent = {"accuracy": accuracy_score(y, call),
                       "balanced_accuracy": balanced_accuracy_score(y, call),
                       "brier": brier_score_loss(y, chosen.p)}
        assert len(chosen) == policy["rows"]
        for name, value in independent.items():
            np.testing.assert_allclose(value, policy["model"][name], rtol=0, atol=1e-12)
        rev_ba = balanced_accuracy_score(y, chosen.past5_excess < 0)
        np.testing.assert_allclose(rev_ba, policy["baselines_on_identical_rows"]["reversal_5d"]["balanced_accuracy"], rtol=0, atol=1e-12)
        checks.append({"requested_coverage": coverage, "independent_metrics": independent, "folds": folds})
        for block in (5, 10, 21, 63):
            rng = np.random.default_rng(0)
            totals = np.zeros((1000, 14))
            for daily in stats:
                indices = c.b.moving_block_indices(len(daily), block, 1000, rng)
                totals += daily[indices].sum(axis=1)
            values = c.interval_statistics(totals)["balanced_accuracy_minus_reversal"]
            assert np.isfinite(values).all()
            ci = np.percentile(values, [2.5, 97.5]).tolist()
            if block == 10:
                np.testing.assert_allclose(ci, policy["paired_uncertainty"]["balanced_accuracy_minus_reversal"]["ci95"], rtol=0, atol=1e-12)
            sensitivity.append({"requested_coverage": coverage, "block_sessions": block, "ci95": ci})
    result = {"independent_metric_checks": checks, "block_sensitivity": sensitivity,
              "draws": 1000, "seed": 0, "validation_scoring": False, "test_scoring": False,
              "purpose": "Exploratory robustness check only; no cutoff or candidate selection."}
    target = c.OUTPUT / "review.json"
    target.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"All independent metric and original-interval checks passed. Wrote {target}")
    for row in sensitivity:
        print(row)


if __name__ == "__main__":
    with threadpool_limits(limits=2):
        main()
