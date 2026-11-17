"""Saved-prediction-only paired ranking audit; never fits or loads new periods."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location("reviewed_targets", Path(__file__).with_name("next-session-target-round.py"))
r = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = r
SPEC.loader.exec_module(r)


def paired_intervals(parts, block):
    rng = np.random.default_rng(0)
    sums = np.zeros((5000, 6))
    total = sum(len(part) for part in parts)
    for part in parts:
        indices = r.b.moving_block_indices(len(part), block, 5000, rng)
        for start in range(0, 5000, 100):
            sums[start:start+100] += part[indices[start:start+100]].sum(axis=1)
    points = np.concatenate(parts).mean(axis=0)
    draws = sums / total
    result = {}
    for index, metric in ((0, "ic"), (1, "spread")):
        for offset, baseline in ((2, "hgb_reference"), (4, "reversal")):
            difference = draws[:, index] - draws[:, index+offset]
            result[f"{metric}_minus_{baseline}"] = {
                "point": float(points[index] - points[index+offset]),
                "ci95": np.quantile(difference, [0.025, 0.975]).tolist(),
                "adjusted_lower": float(np.quantile(difference, 0.025 / 4)),
            }
    return result


def main():
    r.verify()
    results = {}
    for name in r.NAMES[:2]:
        parts, folds = [], []
        for number in range(6):
            r.checkpoint(number)
            rows = pd.read_parquet(r.OUTPUT / f"fold-{number}.parquet")
            reference = pd.read_parquet(r.helpers.PRIOR / f"hgb-fold-{number}.parquet")
            joined = rows.merge(reference[["ticker", "date", "target_date", "label", "p"]],
                                on=["ticker", "date", "target_date", "label"], validate="one_to_one")
            if len(joined) != len(rows) or len(rows) != len(reference):
                raise ValueError("Saved comparison keys changed")
            joined["hgb_reference"] = joined.p
            joined["reversal"] = -joined.previous_return
            ranks = [r.daily_rank(joined, score).set_index("date") for score in (name, "hgb_reference", "reversal")]
            daily = pd.concat(ranks, axis=1, keys=[name, "hgb_reference", "reversal"])
            if not np.isfinite(daily.to_numpy()).all():
                raise ValueError("Undefined rank dates require explicit review")
            parts.append(daily.to_numpy())
            fold = {"fold": number, "dates": len(daily)}
            for score in (name, "hgb_reference", "reversal"):
                fold[score] = {key: float(daily[score][key].mean()) for key in ("ic", "spread")}
            folds.append(fold)
        results[name] = {"folds": folds,
                         "paired_uncertainty": {str(block): paired_intervals(parts, block) for block in (5, 10, 21)}}
        print(name, json.dumps(results[name]), flush=True)
    output = {"analysis": "Post-round paired ranking diagnosis, not a new selection gate",
              "validation_scored": False, "test_scored": False, "new_model_fits": 0,
              "combined_ranking_identical_to_excess": True, "results": results}
    r.write_json(r.ML / "reports/next_session_target_round_ranking_review.json", output)


if __name__ == "__main__":
    main()
