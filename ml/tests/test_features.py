"""Feature engineering (contract 3.4, ml/docs/features.md).

Generic tests run over every feature in FEATURES, so a feature added later is
automatically checked for warm-up, bad_bar handling, look-ahead and price-level use.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from stocksight_data.config import CLEAN_FILE, FEATURES_FILE
from stocksight_data.features import FEATURES, build_features
from stocksight_data.labels import check_feature_columns
from stocksight_data.trading_calendar import sessions_between

PER_TICKER = [n for n, f in FEATURES.items() if f.scope in ("ticker", "cross_section")]
MARKET = [n for n, f in FEATURES.items() if f.scope == "market"]


def make_ohlcv(tickers=("AAA", "BBB", "CCC"), n=600, seed=0) -> pd.DataFrame:
    days = sessions_between(pd.Timestamp("2014-01-02"), pd.Timestamp("2019-12-31"))[:n]
    rng = np.random.default_rng(seed)
    frames = []
    for t in tickers:
        close = 50 * np.cumprod(1 + rng.normal(0.0003, 0.015, n))
        open_ = np.r_[close[0], close[:-1]] * (1 + rng.normal(0, 0.004, n))
        high = np.maximum(open_, close) * (1 + np.abs(rng.normal(0, 0.008, n)) + 1e-4)
        low = np.minimum(open_, close) * (1 - np.abs(rng.normal(0, 0.008, n)) - 1e-4)
        divs = np.where(np.arange(n) % 63 == 30, 0.15, 0.0)
        frames.append(
            pd.DataFrame(
                {
                    "date": days,
                    "ticker": t,
                    "open": open_,
                    "high": high,
                    "low": low,
                    "close": close,
                    "adj_close": close * 0.9,  # a constant back-adjustment factor
                    "volume": pd.array(np.round(1e6 * np.exp(rng.normal(0, 0.3, n))), dtype="Int64"),
                    "dividends": divs,
                    "bad_bar": False,
                }
            )
        )
    return pd.concat(frames, ignore_index=True)


def make_bad(prices: pd.DataFrame, ticker: str, row: int) -> pd.DataFrame:
    """Mark one bar bad the way clean.py does: prices NaN, bad_bar True."""
    out = prices.copy()
    idx = out.index[out["ticker"] == ticker][row]
    out.loc[idx, ["open", "high", "low", "close", "adj_close"]] = np.nan
    out.loc[idx, "bad_bar"] = True
    return out


@pytest.fixture(scope="module")
def panel():
    return make_ohlcv()


@pytest.fixture(scope="module")
def feats(panel):
    return build_features(panel, min_tickers=1)


def ticker_rows(frame, ticker):
    return frame[frame["ticker"] == ticker].reset_index(drop=True)


# ---------------------------------------------------------------- registry
def test_output_columns_match_the_registry_and_pass_the_leakage_guard(feats):
    cols = [c for c in feats.columns if c not in ("ticker", "date")]
    assert cols == list(FEATURES)
    check_feature_columns(cols)


def test_every_feature_documents_a_hypothesis_and_lookback():
    for name, f in FEATURES.items():
        assert f.hypothesis.strip(), name
        assert isinstance(f.lookback, int) and f.lookback >= 0, name
        assert f.scope in ("ticker", "cross_section", "market"), name


def test_output_is_sorted_unique_and_one_row_per_input_row(panel, feats):
    assert len(feats) == len(panel)
    assert feats.equals(feats.sort_values(["ticker", "date"]).reset_index(drop=True))
    assert not feats.duplicated(["ticker", "date"]).any()


# ------------------------------------------------------------ generic checks
@pytest.mark.parametrize("name", PER_TICKER)
def test_warm_up_equals_the_declared_lookback(feats, name):
    col = ticker_rows(feats, "AAA")[name]
    assert col.notna().any(), f"{name} is never defined"
    assert col.first_valid_index() == FEATURES[name].lookback


@pytest.mark.parametrize("name", PER_TICKER)
def test_a_bad_bar_invalidates_exactly_the_windows_that_contain_it(panel, name):
    lookback, row = FEATURES[name].lookback, 300
    col = ticker_rows(build_features(make_bad(panel, "AAA", row), min_tickers=1), "AAA")[name]
    assert col.iloc[row : row + lookback + 1].isna().all(), "a window containing the bad bar was computed"
    assert pd.notna(col.iloc[row + lookback + 1]), "the first window after the bad bar should be valid"


@pytest.mark.parametrize("name", list(FEATURES))
def test_changing_future_data_never_changes_a_feature(panel, feats, name):
    cutoff = pd.Timestamp(sorted(panel["date"].unique())[400])
    changed = panel.copy()
    future = changed["date"] > cutoff
    rng = np.random.default_rng(1)
    scale = rng.uniform(0.5, 1.5, future.sum())
    for c in ["open", "high", "low", "close", "adj_close"]:
        changed.loc[future, c] *= scale
    changed.loc[future, "volume"] = pd.array(np.round(rng.uniform(1e5, 1e7, future.sum())), dtype="Int64")
    after = build_features(changed, min_tickers=1)
    keep = feats["date"] <= cutoff
    # Exact: not even floating-point residue may flow back from future rows.
    pd.testing.assert_series_equal(feats.loc[keep, name], after.loc[keep, name], check_exact=True)


@pytest.mark.parametrize("name", list(FEATURES))
def test_no_feature_depends_on_a_tickers_price_level(panel, feats, name):
    # Re-scaling one ticker's prices (and inversely its volume, as a split does)
    # must change nothing: features are ratios, ranks, or split-invariant dollar volume.
    scaled = panel.copy()
    aaa = scaled["ticker"] == "AAA"
    for c in ["open", "high", "low", "close", "adj_close", "dividends"]:
        scaled.loc[aaa, c] *= 7.3
    scaled["volume"] = scaled["volume"].astype("Float64")
    scaled.loc[aaa, "volume"] = scaled.loc[aaa, "volume"] / 7.3
    after = build_features(scaled, min_tickers=1)
    np.testing.assert_allclose(feats[name], after[name], rtol=1e-5, atol=1e-7, equal_nan=True)


@pytest.mark.parametrize("name", list(FEATURES))
def test_a_later_dividend_back_adjustment_changes_nothing_before_it(panel, feats, name):
    # Yahoo rescales adj_close for all dates before a new ex-dividend date.
    adjusted = panel.copy()
    cutoff = pd.Timestamp(sorted(panel["date"].unique())[400])
    early = (adjusted["ticker"] == "AAA") & (adjusted["date"] <= cutoff)
    adjusted.loc[early, "adj_close"] *= 0.97
    after = build_features(adjusted, min_tickers=1)
    keep = feats["date"] <= cutoff
    np.testing.assert_allclose(feats.loc[keep, name], after.loc[keep, name], rtol=1e-5, atol=1e-7, equal_nan=True)


def test_min_tickers_blanks_cross_sectional_and_market_features(panel):
    f = build_features(panel, min_tickers=4)  # only 3 tickers
    for name, spec in FEATURES.items():
        if spec.scope == "ticker":
            assert f[name].notna().any(), name
        else:
            assert f[name].isna().all(), name


def test_a_missing_session_breaks_windows_like_a_bad_bar(panel):
    gappy = panel.drop(panel.index[(panel["ticker"] == "AAA")][300]).reset_index(drop=True)
    aaa = ticker_rows(build_features(gappy, min_tickers=1), "AAA")
    # Row 300 is now the session after the gap: every 5-day window up to row 304 spans it.
    assert aaa["ret_5d"].iloc[300:305].isna().all()
    assert pd.notna(aaa["ret_5d"].iloc[305])


# -------------------------------------------------------------- hand values
@pytest.fixture(scope="module")
def aaa(panel, feats):
    return ticker_rows(panel, "AAA"), ticker_rows(feats, "AAA")


def test_returns_and_momentum_by_hand(aaa):
    p, f = aaa
    a = p["adj_close"]
    t = 400
    assert f["ret_5d"][t] == pytest.approx(a[t] / a[t - 5] - 1, rel=1e-5)
    assert f["ret_252d"][t] == pytest.approx(a[t] / a[t - 252] - 1, rel=1e-5)
    assert f["mom_12_1"][t] == pytest.approx(a[t - 21] / a[t - 252] - 1, rel=1e-5)


def test_volatility_rsi_and_moving_average_by_hand(aaa):
    p, f = aaa
    a = p["adj_close"].to_numpy()
    r = a[1:] / a[:-1] - 1  # r[i] is the return into row i+1
    t = 400
    window = r[t - 21 : t]  # returns into rows t-20..t
    assert f["vol_21d"][t] == pytest.approx(np.std(window, ddof=1), rel=1e-4)
    w14 = r[t - 14 : t]
    gain, loss = np.clip(w14, 0, None).mean(), np.clip(-w14, 0, None).mean()
    assert f["rsi_14"][t] == pytest.approx(gain / (gain + loss), rel=1e-4)
    assert f["dist_ma_50"][t] == pytest.approx(a[t] / a[t - 49 : t + 1].mean() - 1, rel=1e-4)


def test_candle_gap_volume_and_dividend_features_by_hand(aaa):
    p, f = aaa
    t = 400
    o, h, l, c, a = (p[k] for k in ["open", "high", "low", "close", "adj_close"])
    v = p["volume"].astype(float)
    assert f["close_loc_1d"][t] == pytest.approx((c[t] - l[t]) / (h[t] - l[t]), rel=1e-5)
    assert f["gap_1d"][t] == pytest.approx(o[t] * (a[t] / c[t]) / a[t - 1] - 1, rel=1e-5)
    assert f["volu_ratio_1_21"][t] == pytest.approx(np.log(v[t] / v[t - 21 : t].mean()), rel=1e-4)
    assert f["div_yield_252d"][t] == pytest.approx(p["dividends"][t - 251 : t + 1].sum() / c[t], rel=1e-5)


def test_beta_and_market_features_by_hand(panel, feats):
    wide = panel.pivot(index="date", columns="ticker", values="adj_close")
    r = wide.pct_change()
    mkt = r.mean(axis=1)
    t = 400
    x, y = r["AAA"].iloc[t - 62 : t + 1], mkt.iloc[t - 62 : t + 1]
    beta = np.cov(x, y, ddof=0)[0, 1] / np.var(y)
    f = feats.set_index(["ticker", "date"])
    date = wide.index[t]
    assert f.loc[("AAA", date), "beta_63d"] == pytest.approx(beta, rel=1e-4)
    assert f.loc[("BBB", date), "mkt_ret_21d"] == pytest.approx(np.prod(1 + mkt.iloc[t - 20 : t + 1]) - 1, rel=1e-4)
    assert f.loc[("AAA", date), "ex_ret_5d"] == pytest.approx(
        (wide["AAA"].iloc[t] / wide["AAA"].iloc[t - 5] - 1) - (wide.iloc[t] / wide.iloc[t - 5] - 1).mean(), rel=1e-4
    )


def test_cross_sectional_features_are_centred_and_ranked_per_date(feats):
    by_date = feats.groupby("date")
    assert by_date["ex_ret_21d"].mean().abs().max() < 1e-6
    ranks = feats["rank_ret_21d"].dropna()
    assert ranks.between(0, 1, inclusive="right").all()


# --------------------------------------------- review follow-ups (W3 gaps)
def test_input_order_does_not_matter(panel, feats):
    shuffled = build_features(panel.sample(frac=1.0, random_state=3), min_tickers=1)
    pd.testing.assert_frame_equal(shuffled, feats, check_exact=True)


def test_a_late_listing_ticker_warms_up_from_its_own_first_row():
    base = make_ohlcv(n=600)
    late = make_ohlcv(tickers=("DDD",), n=600, seed=9)
    late = late[late["date"] >= sorted(base["date"].unique())[200]]
    f = ticker_rows(build_features(pd.concat([base, late], ignore_index=True), min_tickers=1), "DDD")
    for name in PER_TICKER:
        assert f[name].first_valid_index() == FEATURES[name].lookback, name


def test_missing_volume_blanks_only_volume_features(panel, feats):
    gappy = panel.copy()
    gappy.loc[gappy.index[gappy["ticker"] == "AAA"][300], "volume"] = pd.NA
    after = ticker_rows(build_features(gappy, min_tickers=1), "AAA")
    before = ticker_rows(feats, "AAA")
    assert pd.isna(after["volu_ratio_1_21"].iloc[300]) and pd.isna(after["volu_ratio_1_21"].iloc[310])
    assert pd.notna(after["volu_ratio_1_21"].iloc[322])  # first row whose prior 21 days exclude row 300
    assert after["ret_5d"].iloc[300] == before["ret_5d"].iloc[300]  # price features unaffected


def test_flat_prices_give_nan_not_inf(panel):
    flat = panel.copy()
    rows = flat.index[flat["ticker"] == "AAA"][300:320]
    for c in ["open", "high", "low", "close", "adj_close"]:
        flat.loc[rows, c] = 40.0
    f = ticker_rows(build_features(flat, min_tickers=1), "AAA")
    window = f.iloc[315:320]
    assert window["rsi_14"].isna().all()  # no up or down moves: undefined, not 0.5
    assert window["close_loc_1d"].isna().all()  # high == low
    numeric = f.drop(columns=["ticker", "date"]).to_numpy(dtype=float)
    assert not np.isinf(numeric).any()


def test_market_features_warm_up_by_date_and_ignore_one_bad_ticker(panel):
    f = ticker_rows(build_features(make_bad(panel, "AAA", 300), min_tickers=1), "BBB")
    for name in MARKET:
        assert f[name].first_valid_index() == FEATURES[name].lookback, name
        assert f[name].iloc[300:330].notna().all(), name  # other tickers still define the market


def test_default_model_features_exclude_market_and_survivorship_suspects():
    from stocksight_data.features import SURVIVORSHIP, model_features

    default = model_features()
    assert not any(FEATURES[n].scope == "market" for n in default)
    assert not any(FEATURES[n].caveat == SURVIVORSHIP for n in default)
    assert {"rank_dollar_vol_63d", "rank_amihud_21d"} <= set(model_features(include_survivorship_suspect=True))
    assert set(MARKET) <= set(model_features(include_market=True))


def test_more_features_by_hand(panel, feats):
    wide = panel.pivot(index="date", columns="ticker", values="adj_close")
    r = wide.pct_change()
    mkt = r.mean(axis=1)
    p = ticker_rows(panel, "AAA")
    f = ticker_rows(feats, "AAA")
    t = 400
    a, c, o, h, l = (p[k].to_numpy() for k in ["adj_close", "close", "open", "high", "low"])
    rr = r["AAA"].to_numpy()
    w63, m63 = rr[t - 62 : t + 1], mkt.to_numpy()[t - 62 : t + 1]
    assert f["skew_63d"][t] == pytest.approx(pd.Series(w63).skew(), rel=1e-3)
    assert f["xvol_63d"][t] == pytest.approx(np.std(w63 - m63, ddof=1), rel=1e-4)
    assert f["corr_mkt_63d"][t] == pytest.approx(np.corrcoef(w63, m63)[0, 1], rel=1e-4)
    assert f["ppo_12_26"][t] == pytest.approx(a[t - 11 : t + 1].mean() / a[t - 25 : t + 1].mean() - 1, rel=1e-4)
    assert f["bb_pos_20"][t] == pytest.approx(
        (a[t] - a[t - 19 : t + 1].mean()) / (2 * np.std(a[t - 19 : t + 1], ddof=1)), rel=1e-4
    )
    assert f["avg_range_21d"][t] == pytest.approx(((h - l) / c)[t - 20 : t + 1].mean(), rel=1e-4)
    assert f["parkinson_vol_21d"][t] == pytest.approx(
        np.sqrt((np.log(h / l)[t - 20 : t + 1] ** 2).mean() / (4 * np.log(2))), rel=1e-4
    )
    assert f["frac_up_21d"][t] == pytest.approx((rr[t - 20 : t + 1] > 0).mean(), rel=1e-6)
    gaps = o[t - 4 : t + 1] * (a / c)[t - 4 : t + 1] / a[t - 5 : t] - 1
    assert f["overnight_ret_5d"][t] == pytest.approx(np.prod(1 + gaps) - 1, rel=1e-4)
    assert f["intraday_ret_5d"][t] == pytest.approx(np.prod(c[t - 4 : t + 1] / o[t - 4 : t + 1]) - 1, rel=1e-4)
    assert f["ex_ret_1d_lag2"][t] == pytest.approx(rr[t - 2] - mkt.iloc[t - 2], rel=1e-4)
    assert f["zret_5d"][t] == pytest.approx(f["ex_ret_5d"][t] / f["vol_21d"][t], rel=1e-5)
    assert f["ret_x_volume_1d"][t] == pytest.approx(f["ret_1d"][t] * f["volu_ratio_1_21"][t], rel=1e-5)


def test_dollar_volume_and_amihud_ranks_by_hand(panel, feats):
    t = 400
    date = sorted(panel["date"].unique())[t]
    dollar, amihud = {}, {}
    for k in ["AAA", "BBB", "CCC"]:
        p = ticker_rows(panel, k)
        dv = p["close"] * p["volume"].astype(float)
        r = p["adj_close"].pct_change().abs()
        dollar[k] = dv[t - 62 : t + 1].mean()
        amihud[k] = (r / dv)[t - 20 : t + 1].mean()
    f = feats[feats["date"] == date].set_index("ticker")
    assert f["rank_dollar_vol_63d"].to_dict() == pytest.approx(pd.Series(dollar).rank(pct=True).to_dict())
    assert f["rank_amihud_21d"].to_dict() == pytest.approx(pd.Series(amihud).rank(pct=True).to_dict())


# ------------------------------------------------------------ real data
@pytest.mark.data
@pytest.mark.skipif(not (CLEAN_FILE.exists() and FEATURES_FILE.exists()), reason="features not built")
def test_stored_features_match_a_brute_force_recomputation():
    """Recompute features for random (ticker, date) rows from that ticker's history <= t only."""
    prices = pd.read_parquet(CLEAN_FILE)
    stored = pd.read_parquet(FEATURES_FILE).set_index(["ticker", "date"])
    sample = stored.sample(400, random_state=7).index
    checked = 0
    for ticker, date in sample:
        hist = prices[(prices["ticker"] == ticker) & (prices["date"] <= date)].tail(260).reset_index(drop=True)
        if len(hist) < 253 or hist["bad_bar"].any():
            continue
        sessions = sessions_between(hist["date"].iloc[0], hist["date"].iloc[-1])
        if len(sessions) != len(hist):  # a missing session in the window
            continue
        a, c = hist["adj_close"].to_numpy(), hist["close"].to_numpy()
        v = hist["volume"].astype(float).to_numpy()
        r = a[1:] / a[:-1] - 1
        expected = {
            "ret_21d": a[-1] / a[-22] - 1,
            "mom_12_1": a[-22] / a[-253] - 1,
            "vol_63d": np.std(r[-63:], ddof=1),
            "dist_high_252": a[-1] / (hist["high"].to_numpy() * a / c)[-252:].max() - 1,
            "div_yield_252d": hist["dividends"].to_numpy()[-252:].sum() / c[-1],
        }
        if not np.isnan(v[-22:]).any():
            expected["volu_ratio_1_21"] = np.log(v[-1] / v[-22:-1].mean())
        row = stored.loc[(ticker, date)]
        for name, value in expected.items():
            assert row[name] == pytest.approx(value, rel=1e-4, abs=1e-6), (ticker, date, name)
        checked += 1
    assert checked >= 200, f"only {checked} rows had clean 260-session histories"
