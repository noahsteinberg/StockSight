"""Purged walk-forward folds inside the training split (contract 3.5, ADR-0005).

Expanding window: fold i fits on rows whose label window ends by fold_ends[i] and
evaluates on rows with as_of_date after fold_ends[i] whose label window ends by
fold_ends[i+1]. Requiring target_date <= boundary purges the last LABEL_HORIZON
as_of_dates before each boundary, so no 5-session label window is shared between
fit and evaluation rows. Every boundary must lie inside the training split, so
model selection never touches validation.
"""

from __future__ import annotations

import pandas as pd

from .config import SPLITS

# Year-end sessions; six 2-year evaluation blocks, 2007-2018.
DEFAULT_FOLD_ENDS = [
    "2006-12-29",
    "2008-12-31",
    "2010-12-31",
    "2012-12-31",
    "2014-12-31",
    "2016-12-30",
    "2018-12-31",
]


def purged_walk_forward(frame: pd.DataFrame, fold_ends=DEFAULT_FOLD_ENDS) -> list[dict]:
    """List of folds: {fold, fit_end, eval_end, train_index, eval_index}.

    `frame` needs `date` (as_of_date) and `target_date`.
    """
    if frame["target_date"].isna().any():
        raise ValueError("frame has rows without a target_date; pass labelled rows only (build_labels output)")
    train_start, train_end = (pd.Timestamp(d) for d in SPLITS["train"])
    ends = [pd.Timestamp(e) for e in fold_ends]
    if any(e > train_end or e < train_start for e in ends) or ends != sorted(ends):
        raise ValueError(f"fold ends must be increasing and inside the train split {SPLITS['train']}")
    folds = []
    for i in range(len(ends) - 1):
        fit_end, eval_end = ends[i], ends[i + 1]
        fit = (frame["date"] >= train_start) & (frame["target_date"] <= fit_end)
        evaluate = (frame["date"] > fit_end) & (frame["target_date"] <= eval_end)
        folds.append(
            {
                "fold": i,
                "fit_end": fit_end,
                "eval_end": eval_end,
                "train_index": frame.index[fit],
                "eval_index": frame.index[evaluate],
            }
        )
    return folds
