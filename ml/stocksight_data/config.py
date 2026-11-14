"""Paths and constants shared by the data pipeline."""

from __future__ import annotations

import os
from pathlib import Path

# Repo root = two levels up from this file (ml/stocksight_data/config.py).
REPO_ROOT = Path(__file__).resolve().parents[2]

# Override with STOCKSIGHT_DATA_DIR if you want the data somewhere else.
DATA_DIR = Path(os.environ.get("STOCKSIGHT_DATA_DIR", REPO_ROOT / "data")) / "sp500"
PRICES_DIR = DATA_DIR / "prices"
TICKERS_FILE = DATA_DIR / "tickers.csv"
MANIFEST_FILE = DATA_DIR / "manifest.json"
CHECK_REPORT_FILE = DATA_DIR / "check_report.json"

# Cleaned, combined dataset (derived from the raw files above; raw is never modified).
CLEAN_DIR = DATA_DIR.parent / "clean"
CLEAN_FILE = CLEAN_DIR / "prices_clean.parquet"
CLEAN_LOG_FILE = CLEAN_DIR / "clean_log.json"
# 2026-11-13 was fetched before Yahoo settled it (see manifest last_bar_provisional).
DEFAULT_CLEAN_END_DATE = "2026-11-12"

MIN_HISTORY_ROWS = 756  # ~3 years of sessions
TINY_PRICE = 0.10  # split-adjusted prices below this lose precision

# Stale pre-listing history (clean rule 2). A ticker is "stale" if more than
# STALE_ZERO_SHARE of its first STALE_DETECT_ROWS rows have zero volume. Its stale
# block then ends at the first run of STALE_CLEAN_RUN_ROWS consecutive rows with
# no zero-volume rows, and the ticker starts there. Only the early block decides
# whether a ticker is trimmed; zero-volume rows later in a history never trigger it.
STALE_DETECT_ROWS = 252
STALE_ZERO_SHARE = 0.5
STALE_CLEAN_RUN_ROWS = 252
# Tickers whose stale trim has been reviewed by hand. If any other ticker
# triggers rule 2, the cleaning step fails before writing so it can be reviewed.
STALE_REVIEWED_TICKERS = {"SW", "FERG", "AMCR"}

# bad_bar column in prices_clean.parquet: True exactly when the row's price columns
# were set to NaN by cleaning, i.e. a bar in EXCLUSIONS below or a flat no-trade bar
# (open == high == low == close with zero/missing volume). The row is kept so the
# date gap stays visible. Downstream code must treat any return or feature window
# that touches a bad_bar row as invalid. Do not forward-fill across it: for
# EXCLUSIONS the distortion is a price-level shift on both sides of the bar.
#
# Known-bad bars (ticker, date, reason). Add more here as they are found.
EXCLUSIONS = [
    ("EXPE", "2011-12-21", "TripAdvisor spin-off + 1:2 reverse split; adj_close still -34%"),
    ("JCI", "2007-07-02", "Tyco 3-way split (Covidien, TE) + 1:4 reverse split; adj_close still -53%"),
]

# Prediction target (ADR-0004): does the stock beat the market over the next
# LABEL_HORIZON NYSE sessions? excess = r5 - market_r5, where market_r5 is the
# equal-weight MARKET_BENCHMARK ("mean" or "median") of r5 across valid tickers on
# date t. Dates with fewer than MIN_TICKERS_PER_DATE valid tickers get no label.
LABEL_HORIZON = 5
MARKET_BENCHMARK = "mean"
MIN_TICKERS_PER_DATE = 150

# Moving-block bootstrap over dates (ADR-0005). Adjacent labels share 4 of 5 return
# days, so dates are resampled in contiguous blocks of this many sessions.
BOOTSTRAP_BLOCK_SESSIONS = 10

# Chronological splits by as_of_date (ADR-0005, ml/docs/prediction-contract.md 3.5).
# A row belongs to a split only if both its as_of_date and its target_date (t+5)
# fall in the range, which purges the last LABEL_HORIZON as_of_dates before each boundary.
# The test end is pinned (not tied to DEFAULT_CLEAN_END_DATE) so refreshing the data
# never moves the "untouched" test set.
SPLITS = {
    "train": ("2000-01-03", "2018-12-31"),
    "validation": ("2019-01-02", "2021-12-31"),
    "test": ("2022-01-03", "2026-11-12"),
}
REPORTS_DIR = DATA_DIR.parent / "reports"
BASELINES_REPORT = REPORTS_DIR / "baselines.json"  # train + validation only
GATES_FILE = REPORTS_DIR / "gates_frozen.json"  # written once by --freeze-gates
TEST_REPORT = REPORTS_DIR / "baselines_test.json"  # only with --include-test
TEST_ACCESS_LOG = REPORTS_DIR / "test_access_log.jsonl"  # one line per test-split evaluation

START_DATE = "2000-01-01"
EXCHANGE = "XNYS"  # NYSE calendar; NASDAQ shares the same regular sessions.

WIKIPEDIA_URL = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
# Wikipedia rejects requests without a descriptive User-Agent.
USER_AGENT = "StockSight-research/0.1 (university course project; python-requests)"

# Column order written to every Parquet file.
PRICE_COLUMNS = [
    "date",
    "ticker",
    "open",
    "high",
    "low",
    "close",
    "adj_close",
    "volume",
    "dividends",
    "stock_splits",
]
