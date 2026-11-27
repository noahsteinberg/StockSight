"""Reviewed company names and sectors for the supported stock universe.

The rows are a static snapshot of one pinned source revision (see
fixtures/STOCK_METADATA_SOURCE.md), not a live feed. A symbol missing from it
stays unknown; nothing is inferred from a ticker.
"""

import csv
import re
from datetime import date
from functools import cache
from pathlib import Path
from typing import Literal, get_args

from pydantic import BaseModel

METADATA_PATH = Path(__file__).resolve().parent / "fixtures" / "stock_metadata.csv"
SYMBOL = re.compile(r"[A-Z][A-Z0-9.-]{0,15}")

Sector = Literal[
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
]
SECTORS: tuple[str, ...] = get_args(Sector)


class MetadataSource(BaseModel):
    name: str
    url: str
    revision_date: date
    retrieved: date
    taxonomy: str
    license: str


SOURCE = MetadataSource(
    name="Wikipedia, List of S&P 500 companies",
    url=(
        "https://en.wikipedia.org/w/index.php"
        "?title=List_of_S%26P_500_companies&oldid=1384572480"
    ),
    revision_date=date(2026, 11, 8),
    retrieved=date(2026, 11, 24),
    taxonomy="GICS sector and sub-industry, as listed by the source",
    license="CC BY-SA 4.0",
)


class StockProfile(BaseModel):
    symbol: str
    company_name: str
    sector: Sector
    sub_industry: str


@cache
def load_metadata() -> dict[str, StockProfile]:
    profiles: dict[str, StockProfile] = {}
    with METADATA_PATH.open(encoding="utf-8", newline="") as file:
        for row in csv.DictReader(file):
            profile = StockProfile.model_validate(
                {key: value.strip() for key, value in row.items()}
            )
            valid = (
                SYMBOL.fullmatch(profile.symbol)
                and profile.symbol not in profiles
                and 0 < len(profile.company_name) <= 120
                and 0 < len(profile.sub_industry) <= 120
            )
            if not valid:
                raise ValueError(f"Invalid stock metadata row for {profile.symbol!r}")
            profiles[profile.symbol] = profile
    return profiles


def profile_for(symbol: str) -> StockProfile | None:
    return load_metadata().get(symbol)


def verified_name(symbol: str, name: str | None) -> str | None:
    """A stored name that only repeats the ticker is the importer's placeholder."""
    cleaned = (name or "").strip()
    return cleaned if cleaned and cleaned.upper() != symbol.upper() else None


def company_name(symbol: str, stored_name: str | None) -> str | None:
    profile = profile_for(symbol)
    return profile.company_name if profile else verified_name(symbol, stored_name)


def symbols_named(query: str) -> list[str]:
    """Symbols whose reviewed company name contains the query, ignoring case."""
    needle = query.casefold()
    return sorted(
        symbol
        for symbol, profile in load_metadata().items()
        if needle in profile.company_name.casefold()
    )


def symbols_in_sector(sector: str) -> list[str]:
    return sorted(
        symbol
        for symbol, profile in load_metadata().items()
        if profile.sector == sector
    )
