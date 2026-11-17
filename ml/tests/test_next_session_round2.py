import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SPEC = importlib.util.spec_from_file_location(
    "next_session_round2", Path(__file__).parents[1] / "scripts" / "next-session-round2.py"
)
r = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = r
SPEC.loader.exec_module(r)


def synthetic_features():
    rows = []
    for date, values in [("2010-01-04", [0.1, -0.2, np.nan]), ("2010-01-05", [0.2, 0.3, -0.1])]:
        for value in values:
            rows.append({"date": date, "ret_1d": value, "ret_5d": value * 2 if np.isfinite(value) else np.nan,
                         "mkt_ret_21d": 0.01, "mkt_vol_21d": 0.02, "xs_dispersion_21d": 0.03})
    return pd.DataFrame(rows)


def test_context_uses_all_feature_rows_before_labels():
    context = r.derive_market_context(synthetic_features(), minimum=2)
    first = context.iloc[0]
    assert first.n_ret_1d == 2
    np.testing.assert_allclose(first.mkt_ret_1d, -0.05)
    np.testing.assert_allclose(first.breadth_1d, 0.5)


def test_sparse_context_is_unavailable():
    context = r.derive_market_context(synthetic_features(), minimum=3)
    assert np.isnan(context.iloc[0].mkt_ret_1d)
    assert np.isnan(context.iloc[0].breadth_5d)
    assert np.isfinite(context.iloc[1].mkt_ret_1d)


def test_inconsistent_existing_market_feature_is_rejected():
    frame = synthetic_features()
    frame.loc[1, "mkt_ret_21d"] = 0.9
    try:
        r.derive_market_context(frame, minimum=2)
    except ValueError as exc:
        assert "not constant" in str(exc)
    else:
        raise AssertionError("inconsistent date-level market value accepted")


def test_configuration_budget_and_model_families_are_frozen():
    configs = r.configurations()
    assert len(configs) == 5
    assert [x.family for x in configs] == ["hgb", "hgb", "hgb", "rf", "extra"]
    assert [x.window_years for x in configs] == [None, 10, 10, 10, 10]
    assert configs[2].params["max_leaf_nodes"] == 31
    assert configs[3].params["n_estimators"] == 300


def test_trailing_window_and_holdout_boundaries():
    dates = pd.bdate_range("2000-01-03", periods=4500)
    rows = pd.DataFrame({"date": dates[:-1], "target_date": dates[1:]})
    expanding, holdout = r.fit_partition(rows, None)
    trailing, holdout_2 = r.fit_partition(rows, 10)
    assert len(trailing) < len(expanding)
    assert holdout.date.nunique() == 252 == holdout_2.date.nunique()
    assert trailing.target_date.max() < holdout.date.min()
    assert trailing.date.min() > trailing.date.max() - pd.DateOffset(years=10)


def test_fixed_selective_rule_reports_coverage():
    rows = pd.DataFrame({"label": [0, 0, 1, 1], "p": [0.2, 0.45, 0.55, 0.8],
                         "date": pd.date_range("2010-01-01", periods=4)})
    result = r.selective(rows)
    assert result["coverage"] == 0.5
    assert result["metrics"]["accuracy"] == 1.0


def test_reference_name_is_not_a_sixth_refit():
    assert r.REFERENCE not in {x.name for x in r.configurations()}
    assert len(r.ALL_FEATURES) == len(r.BASE_FEATURES) + len(r.MARKET_FEATURES)
