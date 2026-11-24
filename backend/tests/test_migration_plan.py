"""Preview real tiny Parquet inputs against disposable SQLite without modifying it."""

from datetime import datetime

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from app.db import Base, database_engine
from app.import_prices import input_hash
from app.migration_plan import inventory, preview
from app.seed import seed_fixture


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "prices.parquet"
    rows = [
        {
            "ticker": symbol,
            "date": datetime(2026, 11, 12),
            "open": 10.0,
            "high": 11.0,
            "low": 9.0,
            "close": 10.0,
            "adj_close": 9.5,
            "volume": 42,
            "dividends": 0.0,
            "stock_splits": 0.0,
            "bad_bar": False,
        }
        for symbol in ("AAPL", "MSFT")
    ]
    pq.write_table(pa.Table.from_pylist(rows), path)
    return path


@pytest.fixture
def engine(tmp_path):
    engine = database_engine(f"sqlite:///{tmp_path / 'preview.sqlite'}")
    Base.metadata.create_all(engine)
    seed_fixture(engine)
    yield engine
    engine.dispose()


def test_pilot_distinguishes_new_symbols_and_replacement_without_writes(source, engine):
    before = inventory(engine)
    result = preview(
        source, {"AAPL", "MSFT"}, before, expected_sha256=input_hash(source)
    )
    assert [(a["symbol"], a["action"]) for a in result["actions"]] == [
        ("AAPL", "replace_canonical_series"),
        ("MSFT", "create"),
    ]
    commands = result["separate_explicit_import_commands"]
    assert commands[0][-3:] == ["--symbols", "MSFT", "--write"]
    assert commands[1][-4:] == [
        "--symbols",
        "AAPL",
        "--write",
        "--replace-existing-series",
    ]
    assert inventory(engine) == before
    assert before["bars"] == 506
    assert result["capacity"]["sampled_rows"] == 2
    assert result["capacity"]["conservative_additional_bytes"] > 0


def test_hash_mismatch_prevents_suggested_write_commands(source, engine):
    result = preview(source, {"MSFT"}, inventory(engine), expected_sha256="0" * 64)
    assert "Source hash differs" in result["blockers"][0]
    assert result["separate_explicit_import_commands"] == []


def test_missing_requested_ticker_is_not_silently_dropped(source, engine):
    result = preview(
        source, {"MSFT", "NVDA"}, inventory(engine), expected_sha256=input_hash(source)
    )
    assert result["blockers"] == ["No accepted history for: NVDA"]
    assert result["separate_explicit_import_commands"] == []


def test_offline_preview_does_not_claim_a_checked_target(source):
    result = preview(source, {"MSFT"}, expected_sha256=input_hash(source))
    assert result["target"] is None
    assert result["actions"][0]["action"] == "uninspected_target"
    assert result["separate_explicit_import_commands"] == []


def test_empty_selection_fails_before_source_access(source):
    with pytest.raises(ValueError, match="explicit symbol subset"):
        preview(source, set())


def test_preview_counts_retained_rows_and_keeps_limit_in_suggested_commands(
    source, engine
):
    rows = pq.read_table(source).to_pylist()
    rows.append({**rows[-1], "date": datetime(2026, 11, 13)})
    pq.write_table(pa.Table.from_pylist(rows), source)
    result = preview(
        source,
        {"MSFT"},
        inventory(engine),
        expected_sha256=input_hash(source),
        max_bars_per_symbol=1,
    )
    assert result["source"]["accepted"] == 2
    assert result["planned_import"] == {"bars": 1, "max_bars_per_symbol": 1}
    assert result["actions"][0]["incoming_bars"] == 1
    assert result["separate_explicit_import_commands"][0][-2:] == [
        "--max-bars-per-symbol",
        "1",
    ]
