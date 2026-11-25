"""The reviewed metadata file is complete, valid and tied to one source revision."""

import csv

from app.stock_metadata import (
    METADATA_PATH,
    SECTORS,
    SOURCE,
    company_name,
    load_metadata,
    symbols_in_sector,
    symbols_named,
)


def test_metadata_file_has_unique_valid_rows():
    with METADATA_PATH.open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    assert len(rows) == len(load_metadata()) == 494
    assert len({row["symbol"] for row in rows}) == 494
    assert {row["sector"] for row in rows} == set(SECTORS)
    assert all(row["company_name"] and row["sub_industry"] for row in rows)


def test_metadata_examples_and_share_classes():
    metadata = load_metadata()
    assert metadata["AAPL"].company_name == "Apple Inc."
    assert metadata["BRK-B"].sector == "Financials"
    assert metadata["BF-B"].sector == "Consumer Staples"
    assert metadata["CBOE"].sub_industry == "Financial Exchanges & Data"
    assert symbols_named("alphabet") == ["GOOG", "GOOGL"]
    assert "XOM" in symbols_in_sector("Energy")


def test_company_name_prefers_review_then_verified_stored_name():
    assert company_name("AAPL", "AAPL") == "Apple Inc."
    assert company_name("NEWCO", "NEWCO") is None
    assert company_name("NEWCO", "New Company Inc.") == "New Company Inc."


def test_source_is_pinned_to_one_revision():
    assert "oldid=" in SOURCE.url
    assert SOURCE.retrieved >= SOURCE.revision_date
