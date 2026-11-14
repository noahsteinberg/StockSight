"""Point-in-time features for the 5-session market-relative target.

Usage (from ml/):  python -m stocksight_data.features     # writes data/features/features.parquet

Rules (prediction contract 3.4, ml/docs/features.md):
  * A feature for (ticker, t) uses only data dated <= t, including cross-sectional
    statistics computed across tickers on date t.
  * A feature with lookback L needs rows t-L..t to exist on consecutive NYSE sessions
    with no bad_bar; otherwise it is NaN. Nothing is filled.
  * No price or volume levels: returns, ratios, ranks, and dollar volume (close x
    volume, which is split-invariant and not dividend-adjusted, used only as ranks).
  * Same-day OHLC ratios use the raw split-adjusted bars; cross-day comparisons use
    bars rescaled by the day's adjustment factor adj_close / close.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import CLEAN_FILE, FEATURES_DIR, FEATURES_FILE, MIN_TICKERS_PER_DATE
from .labels import check_feature_columns
from .trading_calendar import sessions_between

REQUIRED = ["ticker", "date", "open", "high", "low", "close", "adj_close", "volume", "dividends", "bad_bar"]


@dataclass(frozen=True)
class Feature:
    lookback: int  # rows before t the feature needs (window t-lookback..t)
    family: str
    scope: str  # "ticker" (own history), "cross_section" (vs other tickers on t), "market" (same for all on t)
    hypothesis: str
    caveat: str = ""  # "survivorship": its train signal is contaminated by the current-constituents universe


SURVIVORSHIP = "survivorship"


F = Feature
FEATURES: dict[str, Feature] = {
    # --- momentum and reversal (adj_close returns)
    "ret_1d": F(1, "momentum", "ticker", "1-day reversal: yesterday's winners give back part of the move (liquidity provision)."),
    "ret_5d": F(5, "momentum", "ticker", "1-week reversal; the strongest naive baseline on train."),
    "ret_10d": F(10, "momentum", "ticker", "2-week reversal fading into momentum."),
    "ret_21d": F(21, "momentum", "ticker", "1-month reversal (short-term reversal anomaly)."),
    "ret_63d": F(63, "momentum", "ticker", "3-month momentum: information diffuses slowly."),
    "ret_126d": F(126, "momentum", "ticker", "6-month momentum."),
    "ret_252d": F(252, "momentum", "ticker", "12-month momentum including the last month."),
    "mom_12_1": F(252, "momentum", "ticker", "Classic 12-1 momentum: skips the last month to separate it from reversal."),
    "ex_ret_1d": F(1, "momentum", "cross_section", "1-day return relative to the equal-weight market; the target is relative too."),
    "ex_ret_5d": F(5, "momentum", "cross_section", "5-day relative return; same construction as the reversal baseline input."),
    "ex_ret_21d": F(21, "momentum", "cross_section", "1-month relative return."),
    "ex_ret_63d": F(63, "momentum", "cross_section", "3-month relative return."),
    "rank_ret_5d": F(5, "momentum", "cross_section", "Rank of 5-day return on t: robust to outliers and to market-wide moves."),
    "rank_ret_21d": F(21, "momentum", "cross_section", "Rank of 1-month return on t."),
    "rank_mom_12_1": F(252, "momentum", "cross_section", "Rank of 12-1 momentum on t."),
    "zret_5d": F(21, "momentum", "cross_section", "Reversal scaled by the stock's own volatility: a 5% drop means more for a calm stock."),
    "ex_ret_1d_lag1": F(2, "momentum", "cross_section", "Shape of the past week: relative return 1 day before t."),
    "ex_ret_1d_lag2": F(3, "momentum", "cross_section", "Shape of the past week: relative return 2 days before t."),
    "ex_ret_1d_lag3": F(4, "momentum", "cross_section", "Shape of the past week: relative return 3 days before t."),
    "ex_ret_1d_lag4": F(5, "momentum", "cross_section", "Shape of the past week: relative return 4 days before t."),
    "frac_up_21d": F(21, "momentum", "ticker", "Share of up-days: steady gains vs a few jumps carry different information."),
    # --- risk
    "vol_21d": F(21, "risk", "ticker", "Low-volatility anomaly: volatile stocks underperform on a risk-adjusted basis."),
    "vol_63d": F(63, "risk", "ticker", "Slower volatility estimate."),
    "vol_ratio_21_63": F(63, "risk", "ticker", "Rising volatility often follows news or stress."),
    "skew_63d": F(63, "risk", "ticker", "Lottery preference: positively skewed stocks are overpriced."),
    "max_ret_21d": F(21, "risk", "ticker", "MAX effect: stocks with extreme recent up-days underperform."),
    "min_ret_21d": F(21, "risk", "ticker", "Recent crash days: forced selling can overshoot and rebound."),
    "beta_63d": F(63, "risk", "cross_section", "Betting-against-beta: high-beta stocks earn less than their risk implies."),
    "xvol_63d": F(63, "risk", "cross_section", "Volatility of returns relative to the market (idiosyncratic risk)."),
    "rank_vol_63d": F(63, "risk", "cross_section", "Rank of 3-month volatility on t."),
    "corr_mkt_63d": F(63, "risk", "cross_section", "Low market correlation leaves more room for stock-specific moves."),
    "parkinson_vol_21d": F(20, "risk", "ticker", "High-low (Parkinson) volatility: more efficient than close-to-close."),
    # --- candle and range (same-day OHLC)
    "hl_range_1d": F(0, "range", "ticker", "Wide daily range signals disagreement or news."),
    "avg_range_21d": F(20, "range", "ticker", "Average daily range: an alternative volatility estimate using highs and lows."),
    "close_loc_1d": F(0, "range", "ticker", "Closing near the day's high shows buying pressure into the close."),
    "gap_1d": F(1, "range", "ticker", "Overnight gaps partially reverse."),
    "intraday_ret_1d": F(0, "range", "ticker", "Open-to-close move, separated from the overnight gap."),
    "overnight_ret_5d": F(5, "range", "ticker", "Overnight returns over a week (news, earnings) behave differently from intraday ones."),
    "intraday_ret_5d": F(4, "range", "ticker", "Intraday returns over a week (trading pressure)."),
    # --- trend and oscillators (simple moving averages; strict windows)
    "dist_ma_10": F(9, "trend", "ticker", "Short-term stretch from the 10-day average tends to revert."),
    "dist_ma_50": F(49, "trend", "ticker", "Medium-term trend position."),
    "dist_ma_200": F(199, "trend", "ticker", "Long-term trend position."),
    "ma_ratio_50_200": F(199, "trend", "ticker", "Golden/death cross as a continuous variable."),
    "ppo_12_26": F(25, "trend", "ticker", "MACD-style trend strength (SMA version, scale-free)."),
    "dist_high_21": F(20, "trend", "ticker", "Distance from the 1-month high: short-term overbought/oversold."),
    "dist_high_252": F(251, "trend", "ticker", "52-week-high anchoring: stocks near their high keep outperforming."),
    "dist_low_252": F(251, "trend", "ticker", "Distance from the 52-week low."),
    "rsi_14": F(14, "trend", "ticker", "Overbought/oversold oscillator (share of up-moves in 14 days)."),
    "bb_pos_20": F(19, "trend", "ticker", "Bollinger position: price stretch in units of its own volatility."),
    # --- volume and liquidity
    "volu_ratio_1_21": F(21, "volume", "ticker", "Unusual volume today marks news or attention."),
    "volu_ratio_5_63": F(62, "volume", "ticker", "A week of elevated volume vs the quarter."),
    "rank_volu_ratio_1_21": F(21, "volume", "cross_section", "Rank of today's volume surge across stocks on t."),
    "ret_x_volume_1d": F(21, "volume", "ticker", "Moves on heavy volume (information) reverse less than moves on light volume (noise)."),
    "rank_dollar_vol_63d": F(62, "volume", "cross_section", "Size/liquidity proxy: smaller, less liquid stocks behave differently.", SURVIVORSHIP),
    "rank_amihud_21d": F(21, "volume", "cross_section", "Illiquidity (|return| per dollar traded): an illiquidity premium.", SURVIVORSHIP),
    # --- income
    "div_yield_252d": F(251, "income", "ticker", "Trailing dividend yield: value and defensiveness."),
    # --- market state (identical for every stock on t; useful only in interactions)
    "mkt_ret_21d": F(21, "market", "market", "Market regime: reversal and momentum strength depend on recent market moves."),
    "mkt_vol_21d": F(21, "market", "market", "Market stress regime."),
    "xs_dispersion_21d": F(21, "market", "market", "Cross-sectional dispersion: how much room there is for stock picking."),
}
del F


def model_features(include_market: bool = False, include_survivorship_suspect: bool = False) -> list[str]:
    """Default model inputs.

    Excludes market-state features (constant on a date: trees can fingerprint dates)
    and survivorship-suspect features (size/liquidity ranks whose train signal partly
    reflects that today's small members are the past's winners) unless asked for.
    """
    return [
        name
        for name, f in FEATURES.items()
        if (include_market or f.scope != "market") and (include_survivorship_suspect or f.caveat != SURVIVORSHIP)
    ]


def _prepare(prices: pd.DataFrame) -> pd.DataFrame:
    missing = set(REQUIRED) - set(prices.columns)
    if missing:
        raise ValueError(f"prices is missing columns {sorted(missing)}")
    df = prices[REQUIRED].copy()
    df["date"] = pd.to_datetime(df["date"]).astype("datetime64[ns]").dt.normalize()
    df["bad_bar"] = df["bad_bar"].astype(bool)
    df = df.sort_values(["ticker", "date"], kind="stable").reset_index(drop=True)
    sessions = sessions_between(df["date"].min(), df["date"].max())
    df["session"] = sessions.get_indexer(pd.DatetimeIndex(df["date"]))
    return df


def clean_run_length(df: pd.DataFrame) -> pd.Series:
    """Consecutive clean rows ending at each row (same ticker, consecutive sessions, no bad_bar)."""
    clean = ~df["bad_bar"] & df["adj_close"].notna() & (df["session"] >= 0)
    same_ticker = df["ticker"].eq(df["ticker"].shift())
    continues = clean & clean.shift(fill_value=False) & same_ticker & (df["session"].diff() == 1)
    run_id = (~continues).cumsum()
    run = df.groupby(run_id, sort=False).cumcount() + 1
    return run.where(clean, 0)


def build_features(prices: pd.DataFrame, min_tickers: int = MIN_TICKERS_PER_DATE) -> pd.DataFrame:
    """ticker, date and every feature in FEATURES (float32, NaN when invalid).

    Returns one row per input row, sorted by (ticker, date) regardless of input order;
    merge on (ticker, date), not on position.
    """
    df = _prepare(prices)
    run = clean_run_length(df)
    by_ticker = df.groupby("ticker", sort=False)

    def valid(lookback: int) -> pd.Series:
        return run >= lookback + 1

    def roll(s: pd.Series, w: int):
        # Per-ticker rolling: no arithmetic ever crosses from one ticker into another.
        return s.groupby(df["ticker"], sort=False).rolling(w, min_periods=w)

    def done(r) -> pd.Series:
        return r.reset_index(level=0, drop=True).sort_index()

    def xs_count(s: pd.Series) -> pd.Series:
        return s.groupby(df["date"]).transform("count")

    def xs_demean(s: pd.Series) -> pd.Series:
        ok = xs_count(s) >= min_tickers
        return (s - s.groupby(df["date"]).transform("mean")).where(ok)

    def xs_rank(s: pd.Series) -> pd.Series:
        ok = xs_count(s) >= min_tickers
        return s.groupby(df["date"]).rank(pct=True).where(ok)

    a, close = df["adj_close"], df["close"]
    factor = a / close  # adjustment factor of the day; rescales same-day bars for cross-day ratios
    adj_open, adj_high, adj_low = df["open"] * factor, df["high"] * factor, df["low"] * factor
    volume = pd.Series(df["volume"].astype("Float64").to_numpy(dtype=float, na_value=np.nan), index=df.index)
    dollar = close * volume  # split-invariant, point-in-time dollar volume

    def ret(k: int) -> pd.Series:
        return (a / by_ticker["adj_close"].shift(k) - 1).where(valid(k))

    out: dict[str, pd.Series] = {}
    r1 = ret(1)
    for k in (1, 5, 10, 21, 63, 126, 252):
        out[f"ret_{k}d"] = ret(k)
    out["mom_12_1"] = (by_ticker["adj_close"].shift(21) / by_ticker["adj_close"].shift(252) - 1).where(valid(252))

    # Market: equal-weight mean of valid 1-day returns per date (dates with enough tickers only).
    m_daily = r1.groupby(df["date"]).mean().where(r1.groupby(df["date"]).count() >= min_tickers)
    mkt1 = df["date"].map(m_daily)

    for k in (1, 5, 21, 63):
        out[f"ex_ret_{k}d"] = xs_demean(out[f"ret_{k}d"])
    out["rank_ret_5d"] = xs_rank(out["ret_5d"])
    out["rank_ret_21d"] = xs_rank(out["ret_21d"])
    out["rank_mom_12_1"] = xs_rank(out["mom_12_1"])
    for lag in (1, 2, 3, 4):
        lagged = out["ex_ret_1d"].groupby(df["ticker"], sort=False).shift(lag)
        out[f"ex_ret_1d_lag{lag}"] = lagged.where(valid(lag + 1))
    up = (r1 > 0).astype(float).where(r1.notna())
    out["frac_up_21d"] = done(roll(up, 21).mean()).where(valid(21))

    out["vol_21d"] = done(roll(r1, 21).std()).where(valid(21))
    out["vol_63d"] = done(roll(r1, 63).std()).where(valid(63))
    out["vol_ratio_21_63"] = out["vol_21d"] / out["vol_63d"]
    out["skew_63d"] = done(roll(r1, 63).skew()).where(valid(63))
    out["max_ret_21d"] = done(roll(r1, 21).max()).where(valid(21))
    out["min_ret_21d"] = done(roll(r1, 21).min()).where(valid(21))
    cov = done(roll(r1 * mkt1, 63).mean()) - done(roll(r1, 63).mean()) * done(roll(mkt1, 63).mean())
    var = done(roll(mkt1 * mkt1, 63).mean()) - done(roll(mkt1, 63).mean()) ** 2
    out["beta_63d"] = (cov / var).where(valid(63))
    var_x = done(roll(r1 * r1, 63).mean()) - done(roll(r1, 63).mean()) ** 2
    out["corr_mkt_63d"] = (cov / np.sqrt(var_x * var)).where(valid(63) & (var_x > 0) & (var > 0))
    out["xvol_63d"] = done(roll(r1 - mkt1, 63).std()).where(valid(63))
    out["rank_vol_63d"] = xs_rank(out["vol_63d"])
    out["zret_5d"] = (out["ex_ret_5d"] / out["vol_21d"]).where(out["vol_21d"] > 0)
    log_hl_sq = np.log(df["high"] / df["low"]) ** 2
    out["parkinson_vol_21d"] = np.sqrt(done(roll(log_hl_sq, 21).mean()) / (4 * np.log(2))).where(valid(20))

    hl = (df["high"] - df["low"]) / close
    out["hl_range_1d"] = hl.where(valid(0))
    out["avg_range_21d"] = done(roll(hl, 21).mean()).where(valid(20))
    span = df["high"] - df["low"]
    out["close_loc_1d"] = ((close - df["low"]) / span).where(valid(0) & (span > 0))
    gap = adj_open / by_ticker["adj_close"].shift(1) - 1
    intraday = close / df["open"] - 1
    out["gap_1d"] = gap.where(valid(1))
    out["intraday_ret_1d"] = intraday.where(valid(0))
    out["overnight_ret_5d"] = np.expm1(done(roll(np.log1p(gap), 5).sum())).where(valid(5))
    out["intraday_ret_5d"] = np.expm1(done(roll(np.log1p(intraday), 5).sum())).where(valid(4))

    def ma(w: int) -> pd.Series:
        return done(roll(a, w).mean())

    out["dist_ma_10"] = (a / ma(10) - 1).where(valid(9))
    out["dist_ma_50"] = (a / ma(50) - 1).where(valid(49))
    out["dist_ma_200"] = (a / ma(200) - 1).where(valid(199))
    out["ma_ratio_50_200"] = (ma(50) / ma(200) - 1).where(valid(199))
    out["ppo_12_26"] = (ma(12) / ma(26) - 1).where(valid(25))
    out["dist_high_21"] = (a / done(roll(adj_high, 21).max()) - 1).where(valid(20))
    out["dist_high_252"] = (a / done(roll(adj_high, 252).max()) - 1).where(valid(251))
    out["dist_low_252"] = (a / done(roll(adj_low, 252).min()) - 1).where(valid(251))
    gain = done(roll(r1.clip(lower=0), 14).mean())
    loss = done(roll((-r1).clip(lower=0), 14).mean())
    out["rsi_14"] = (gain / (gain + loss)).where(valid(14))
    out["bb_pos_20"] = ((a - ma(20)) / (2 * done(roll(a, 20).std()))).where(valid(19))

    def log_ratio(num: pd.Series, den: pd.Series) -> pd.Series:
        ok = (num > 0) & (den > 0)
        return np.log(num.where(ok) / den.where(ok))

    prior_mean_21 = done(roll(volume, 21).mean()).groupby(df["ticker"], sort=False).shift(1)
    out["volu_ratio_1_21"] = log_ratio(volume, prior_mean_21).where(valid(21))
    out["volu_ratio_5_63"] = log_ratio(done(roll(volume, 5).mean()), done(roll(volume, 63).mean())).where(valid(62))
    out["rank_volu_ratio_1_21"] = xs_rank(out["volu_ratio_1_21"])
    out["ret_x_volume_1d"] = out["ret_1d"] * out["volu_ratio_1_21"]
    out["rank_dollar_vol_63d"] = xs_rank(done(roll(dollar, 63).mean()).where(valid(62)))
    amihud = done(roll(r1.abs() / dollar.where(dollar > 0), 21).mean()).where(valid(21))
    out["rank_amihud_21d"] = xs_rank(amihud)

    out["div_yield_252d"] = (done(roll(df["dividends"], 252).sum()) / close).where(valid(251))

    m_log = np.log1p(m_daily)
    out["mkt_ret_21d"] = df["date"].map(np.expm1(m_log.rolling(21, min_periods=21).sum()))
    out["mkt_vol_21d"] = df["date"].map(m_daily.rolling(21, min_periods=21).std())
    disp = out["ret_21d"].groupby(df["date"]).std().where(out["ret_21d"].groupby(df["date"]).count() >= min_tickers)
    out["xs_dispersion_21d"] = df["date"].map(disp)

    unknown = set(out) ^ set(FEATURES)
    if unknown:
        raise RuntimeError(f"feature registry and implementation differ: {sorted(unknown)}")
    check_feature_columns(list(FEATURES))
    result = pd.DataFrame({"ticker": df["ticker"], "date": df["date"]})
    for name in FEATURES:
        values = out[name].replace([np.inf, -np.inf], np.nan)
        result[name] = values.astype("float32")
    return result


def main() -> None:
    argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    prices = pd.read_parquet(CLEAN_FILE)
    feats = build_features(prices)
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    tmp = FEATURES_FILE.with_suffix(".parquet.tmp")
    feats.to_parquet(tmp, index=False)
    tmp.replace(FEATURES_FILE)
    from .baselines import _environment, _git_state, sha256_file  # provenance helpers

    meta = {
        "created_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds"),
        "dataset_sha256": sha256_file(CLEAN_FILE),
        "features_sha256": sha256_file(FEATURES_FILE),
        "code": _git_state(),
        "environment": _environment(),
        "min_tickers_per_date": MIN_TICKERS_PER_DATE,
        "rows": int(len(feats)),
        "features": {n: {"lookback": f.lookback, "family": f.family, "scope": f.scope, "caveat": f.caveat}
                     for n, f in FEATURES.items()},
        "default_model_features": model_features(),
    }
    FEATURES_FILE.with_name("features.meta.json").write_text(json.dumps(meta, indent=2))
    coverage = feats[list(FEATURES)].notna().mean().sort_values()
    print(f"Wrote {FEATURES_FILE}: {len(feats):,} rows x {len(FEATURES)} features")
    print("Lowest coverage (share of rows with a value):")
    print(json.dumps({k: round(float(v), 4) for k, v in coverage.head(8).items()}, indent=1))


if __name__ == "__main__":
    main()
