"""Fetch the current S&P 500 constituent list (with GICS sectors) from Wikipedia.

Usage (from ml/):  python -m stocksight_data.universe
"""

from __future__ import annotations

import argparse
from io import StringIO

import pandas as pd
import requests

from .config import DATA_DIR, TICKERS_FILE, USER_AGENT, WIKIPEDIA_URL

RENAME = {
    "Symbol": "symbol",
    "Security": "name",
    "GICS Sector": "sector",
    "GICS Sub-Industry": "sub_industry",
    "Headquarters Location": "headquarters",
    "Date added": "date_added",
    "CIK": "cik",
    "Founded": "founded",
}


def to_yahoo_symbol(symbol: str) -> str:
    """Wikipedia/S&P use class dots (BRK.B); Yahoo uses dashes (BRK-B)."""
    return symbol.strip().upper().replace(".", "-")


def fetch_constituents() -> pd.DataFrame:
    resp = requests.get(WIKIPEDIA_URL, headers={"User-Agent": USER_AGENT}, timeout=30)
    resp.raise_for_status()
    # The constituents table has id="constituents"; matching on it avoids
    # accidentally grabbing the "selected changes" table further down the page.
    tables = pd.read_html(StringIO(resp.text), attrs={"id": "constituents"})
    if not tables:
        raise RuntimeError("Could not find the constituents table on Wikipedia")
    df = tables[0].rename(columns=RENAME)
    missing = {"symbol", "name", "sector"} - set(df.columns)
    if missing:
        raise RuntimeError(f"Wikipedia table layout changed; missing columns {missing}")

    df["symbol"] = df["symbol"].astype(str).str.strip()
    df.insert(1, "yf_symbol", df["symbol"].map(to_yahoo_symbol))
    df = df.drop_duplicates("yf_symbol").sort_values("yf_symbol").reset_index(drop=True)

    # Sanity bounds: the index has ~500 companies and ~503 share classes.
    if not 480 <= len(df) <= 520:
        raise RuntimeError(f"Unexpected constituent count: {len(df)}")
    return df


def save_universe() -> pd.DataFrame:
    df = fetch_constituents()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(TICKERS_FILE, index=False)
    return df


def main() -> None:
    argparse.ArgumentParser(description=__doc__).parse_args()
    df = save_universe()
    changed = df[df["symbol"] != df["yf_symbol"]]
    print(f"Saved {len(df)} tickers to {TICKERS_FILE}")
    print(f"Symbols rewritten for Yahoo: {', '.join(f'{a}->{b}' for a, b in zip(changed.symbol, changed.yf_symbol)) or 'none'}")
    print("\nTickers per sector:")
    print(df["sector"].value_counts().to_string())


if __name__ == "__main__":
    main()
