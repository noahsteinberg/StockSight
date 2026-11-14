# StockSight features (v1)

59 point-in-time features for the 5-session market-relative target ([prediction contract](prediction-contract.md), [ADR-0006](../../docs/adr/0006-feature-design.md)).

- Code: `stocksight_data/features.py`. The registry `FEATURES` gives each feature's lookback, family, scope, hypothesis and caveat.
- Build: `python -m stocksight_data.features` writes `data/features/features.parquet`, plus `features.meta.json`. The metadata file records the dataset SHA-256, git state, library versions and the default feature set.
- Report: `python -m stocksight_data.feature_report` writes `data/reports/feature_report.json`.

## Design rules (enforced by tests)
1. **Point in time.** A feature for (ticker, t) uses only data dated ≤ t. Cross-sectional statistics are computed across tickers on date t.
   - Tests change every price and volume after a cutoff and require *bit-identical* features before it.
2. **Strict windows.** A feature with lookback L needs rows t-L..t on consecutive NYSE sessions, with no `bad_bar`. Otherwise it is NaN, never filled.
   - Tests check, for every feature: warm-up = L; a bad bar blanks exactly the windows that contain it; a missing session breaks windows; a late-listing ticker warms up from its own first row.
3. **No levels.** Features are returns, ratios and ranks.
   - Tests rescale one ticker's prices (and its volume inversely, as a split would) and require identical features. They also apply a later dividend back-adjustment and require that nothing before it changes.
   - Dollar volume (close × volume) is the one level-like input. It is split-invariant and not dividend-adjusted, so it is point-in-time. It is used only as a cross-sectional rank.
4. **Consistent OHLC.** Same-day ratios use raw bars. Cross-day comparisons rescale open, high and low by that day's `adj_close / close`.
5. **Strict oscillators.** RSI and PPO use simple moving averages, not EMAs, so every window has a hard length.
6. **Leakage guard.** `labels.check_feature_columns` rejects forward-looking label columns and `tickers.csv` membership fields.

Verification:
- **Unit tests:** 400 pass.
- **Planted bugs:** six, each caught: no validity mask, returns from future prices, ranks over all dates instead of per date, an off-by-one lookback, a price-level feature, and rolling windows that cross tickers.
- **Brute-force recomputation:** at least 200 random real (ticker, date) rows match an explicit per-row calculation.
- **Review:** `mle-reviewer` gave APPROVE WITH WARNINGS. Its warnings are addressed below.

## Train-only signal
Method: per-date Spearman IC between each feature and `excess_ret`, train split only.
- Labels are computed from prices cut at 2018-12-31, so validation outcomes are never computed.
- The 95% CI is a moving-block bootstrap of the mean IC (block 10).
- `*` means the feature survives Benjamini-Hochberg false-discovery control at 5% across all features.

**IC measures one feature alone.** It is guidance for the modelling step, not a gate.

| Feature | Family | Scope | Lookback | Train IC | 2000-09 / 2010-18 | In default set |
|---|---|---|---|---|---|---|
| `ret_1d` | momentum | ticker | 1 | -0.0192 * | -0.0261 / -0.0115 | yes |
| `ret_5d` | momentum | ticker | 5 | -0.0248 * | -0.0322 / -0.0167 | yes |
| `ret_10d` | momentum | ticker | 10 | -0.0237 * | -0.0308 / -0.0159 | yes |
| `ret_21d` | momentum | ticker | 21 | -0.0164 * | -0.0207 / -0.0117 | yes |
| `ret_63d` | momentum | ticker | 63 | -0.0092 | -0.0159 / -0.0018 | yes |
| `ret_126d` | momentum | ticker | 126 | -0.0021 | -0.0061 / +0.0022 | yes |
| `ret_252d` | momentum | ticker | 252 | +0.0051 | -0.0008 / +0.0110 | yes |
| `mom_12_1` | momentum | ticker | 252 | +0.0114 | +0.0077 / +0.0150 | yes |
| `ex_ret_1d` | momentum | cross_section | 1 | -0.0192 * | -0.0261 / -0.0115 | yes |
| `ex_ret_5d` | momentum | cross_section | 5 | -0.0248 * | -0.0322 / -0.0167 | yes |
| `ex_ret_21d` | momentum | cross_section | 21 | -0.0164 * | -0.0207 / -0.0117 | yes |
| `ex_ret_63d` | momentum | cross_section | 63 | -0.0092 | -0.0159 / -0.0018 | yes |
| `rank_ret_5d` | momentum | cross_section | 5 | -0.0248 * | -0.0322 / -0.0167 | yes |
| `rank_ret_21d` | momentum | cross_section | 21 | -0.0164 * | -0.0207 / -0.0117 | yes |
| `rank_mom_12_1` | momentum | cross_section | 252 | +0.0114 | +0.0077 / +0.0150 | yes |
| `zret_5d` | momentum | cross_section | 21 | -0.0240 * | -0.0315 / -0.0156 | yes |
| `ex_ret_1d_lag1` | momentum | cross_section | 2 | -0.0135 * | -0.0191 / -0.0073 | yes |
| `ex_ret_1d_lag2` | momentum | cross_section | 3 | -0.0099 * | -0.0129 / -0.0065 | yes |
| `ex_ret_1d_lag3` | momentum | cross_section | 4 | -0.0085 * | -0.0106 / -0.0061 | yes |
| `ex_ret_1d_lag4` | momentum | cross_section | 5 | -0.0082 * | -0.0094 / -0.0067 | yes |
| `frac_up_21d` | momentum | ticker | 21 | -0.0119 * | -0.0170 / -0.0062 | yes |
| `vol_21d` | risk | ticker | 21 | +0.0040 | +0.0025 / +0.0057 | yes |
| `vol_63d` | risk | ticker | 63 | +0.0055 | +0.0031 / +0.0082 | yes |
| `vol_ratio_21_63` | risk | ticker | 63 | +0.0006 | +0.0019 / -0.0007 | yes |
| `skew_63d` | risk | ticker | 63 | -0.0027 | -0.0057 / +0.0005 | yes |
| `max_ret_21d` | risk | ticker | 21 | +0.0001 | -0.0020 / +0.0024 | yes |
| `min_ret_21d` | risk | ticker | 21 | -0.0058 | -0.0069 / -0.0047 | yes |
| `beta_63d` | risk | cross_section | 63 | +0.0004 | -0.0033 / +0.0044 | yes |
| `xvol_63d` | risk | cross_section | 63 | +0.0043 | +0.0023 / +0.0064 | yes |
| `rank_vol_63d` | risk | cross_section | 63 | +0.0055 | +0.0031 / +0.0082 | yes |
| `corr_mkt_63d` | risk | cross_section | 63 | -0.0055 | -0.0089 / -0.0018 | yes |
| `parkinson_vol_21d` | risk | ticker | 20 | +0.0066 | +0.0048 / +0.0087 | yes |
| `hl_range_1d` | range | ticker | 0 | +0.0041 | +0.0043 / +0.0039 | yes |
| `avg_range_21d` | range | ticker | 20 | +0.0066 | +0.0046 / +0.0088 | yes |
| `close_loc_1d` | range | ticker | 0 | -0.0221 * | -0.0339 / -0.0089 | yes |
| `gap_1d` | range | ticker | 1 | -0.0038 | -0.0017 / -0.0062 | yes |
| `intraday_ret_1d` | range | ticker | 0 | -0.0176 * | -0.0257 / -0.0086 | yes |
| `overnight_ret_5d` | range | ticker | 5 | -0.0059 * | -0.0045 / -0.0075 | yes |
| `intraday_ret_5d` | range | ticker | 4 | -0.0218 * | -0.0298 / -0.0129 | yes |
| `dist_ma_10` | trend | ticker | 9 | -0.0269 * | -0.0351 / -0.0178 | yes |
| `dist_ma_50` | trend | ticker | 49 | -0.0184 * | -0.0254 / -0.0108 | yes |
| `dist_ma_200` | trend | ticker | 199 | -0.0077 | -0.0138 / -0.0015 | yes |
| `ma_ratio_50_200` | trend | ticker | 199 | +0.0032 | +0.0019 / +0.0045 | yes |
| `ppo_12_26` | trend | ticker | 25 | -0.0128 * | -0.0158 / -0.0095 | yes |
| `dist_high_21` | trend | ticker | 20 | -0.0225 * | -0.0305 / -0.0138 | yes |
| `dist_high_252` | trend | ticker | 251 | -0.0135 | -0.0194 / -0.0076 | yes |
| `dist_low_252` | trend | ticker | 251 | +0.0009 | -0.0050 / +0.0068 | yes |
| `rsi_14` | trend | ticker | 14 | -0.0198 * | -0.0274 / -0.0115 | yes |
| `bb_pos_20` | trend | ticker | 19 | -0.0209 * | -0.0284 / -0.0126 | yes |
| `volu_ratio_1_21` | volume | ticker | 21 | +0.0072 * | +0.0135 / +0.0003 | yes |
| `volu_ratio_5_63` | volume | ticker | 62 | -0.0003 | +0.0057 / -0.0068 | yes |
| `rank_volu_ratio_1_21` | volume | cross_section | 21 | +0.0072 * | +0.0135 / +0.0003 | yes |
| `ret_x_volume_1d` | volume | ticker | 21 | +0.0022 | +0.0040 / +0.0002 | yes |
| `rank_dollar_vol_63d` | volume | cross_section | 62 | -0.0219 * | -0.0252 / -0.0184 | no (survivorship) |
| `rank_amihud_21d` | volume | cross_section | 21 | +0.0234 * | +0.0253 / +0.0213 | no (survivorship) |
| `div_yield_252d` | income | ticker | 251 | -0.0068 | -0.0000 / -0.0136 | yes |
| `mkt_ret_21d` | market | market | 21 | n/a | n/a | no (market state) |
| `mkt_vol_21d` | market | market | 21 | n/a | n/a | no (market state) |
| `xs_dispersion_21d` | market | market | 21 | n/a | n/a | no (market state) |

## What the report says
- **Short-term reversal dominates.** Price stretch over 1–21 days predicts lagging the market:
  - returns, the distance from the 10-day average, closing location, RSI, Bollinger position;
  - every one of the last 5 daily relative returns.
  - The reversal is mostly **intraday** (5-day intraday IC −0.022 vs overnight −0.006).
- **The edge is decaying.** Most reversal ICs roughly halve from 2000–09 to 2010–18. This fits validation, where the reversal baseline was no longer significant.
- **Not significant after adjustment:** 12-1 momentum (+0.011), the 52-week high, overnight gaps, volatility, beta, skew, MAX. Several flip sign between decades.
- **Size and liquidity look strong, but are survivorship-contaminated.** Stocks that were small or illiquid in 2000–2018 *and* are in today's index are, by construction, the ones that grew. `rank_dollar_vol_63d` and `rank_amihud_21d` are therefore flagged, and excluded from the default model set.
- **Redundant pairs (|ρ| ≥ 0.9):**
  - the `ex_ret_5d` / `rank_ret_5d` / `zret_5d` trio, and `ex_ret_21d` / `rank_ret_21d`;
  - `parkinson_vol_21d` / `avg_range_21d` / `vol_21d`, and `vol_63d` / `xvol_63d`;
  - `ret_252d` / `mom_12_1`, and `ret_126d` / `dist_ma_200`;
  - dollar volume / Amihud.
  - Raw `ret_k` and `ex_ret_k` differ only by a per-date constant. That gives identical per-date IC, but not identical behaviour in a pooled model.

## Recommendations for the modelling step
- **Start from `features.model_features()`** (54 features). It excludes market-state features, which are constant per date and let trees fingerprint dates, and the two survivorship-suspect ranks. Add each excluded group back only as a separate, recorded experiment.
- **Heavy tails:**
  - Returns have 0.02–0.1% of values beyond 10 SD. `ret_252d` reaches 64×, and `div_yield_252d` reaches 4.75 (a special dividend).
  - For logistic regression, winsorise at train percentiles, or use per-date ranks. Fit any transform on training folds only (contract 3.4 rule 4).
  - Prefer the `ex_` and `rank_` versions for this relative target.
- **Missing values follow ticker age.** Coverage runs from 0.94 (252-day features) to 1.0. Dropping incomplete rows removes each ticker's first year. Use explicit warm-up tiers, or impute with a missing-indicator fitted on train.
- **Select with walk-forward folds inside train** (`stocksight_data.folds.purged_walk_forward`, six 2-year evaluation blocks, 2007–2018). Validation is used once per finalist, through `baselines.gate_model`.
