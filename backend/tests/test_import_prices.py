"""Importer tests use tiny synthetic Parquet files and disposable storage only."""

from datetime import datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import Base, DailyBar, database_engine
from app.import_prices import import_snapshot, scan, validated_row, write_symbol
from app.repository import database_history, search_database
from app.seed import seed_fixture

pa = pytest.importorskip("pyarrow")
pq = pytest.importorskip("pyarrow.parquet")


def row(symbol="AAPL", day=1, **updates):
    return {
        "date": datetime(2020, 1, day),
        "ticker": symbol,
        "open": 10.0,
        "high": 11.0,
        "low": 9.0,
        "close": 10.0,
        "adj_close": 8.5,
        "volume": 42,
        "dividends": 0.25,
        "stock_splits": 0.0,
        "bad_bar": False,
        **updates,
    }


def parquet(path, rows):
    schema = pa.schema(
        [
            ("date", pa.timestamp("ms")),
            ("ticker", pa.large_string()),
            *[
                (name, pa.float64())
                for name in ("open", "high", "low", "close", "adj_close")
            ],
            ("volume", pa.int64()),
            ("dividends", pa.float64()),
            ("stock_splits", pa.float64()),
            ("bad_bar", pa.bool_()),
        ]
    )
    pq.write_table(pa.Table.from_pylist(rows, schema=schema), path)


@pytest.fixture
def engine(tmp_path):
    engine = database_engine(f"sqlite:///{tmp_path / 'import.sqlite'}")
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


def test_validation_quarantines_rows_without_repair(tmp_path):
    path = tmp_path / "prices.parquet"
    parquet(
        path,
        [
            row(),
            row(day=2, bad_bar=True, close=None),
            row(day=3, volume=None),
            row("MSFT", open=8.0),
            row("MSFT", day=2),
        ],
    )
    report = scan(path)
    assert report["selected_rows"] == 5
    assert report["accepted"] == 2
    assert report["quarantined"] == 3
    assert report["reason_counts"] == {
        "flagged_bar": 1,
        "missing_value": 2,
        "ohlc_bounds": 1,
        "rounded_bounds": 1,
    }
    assert report["accepted_by_symbol"] == {"AAPL": 1, "MSFT": 1}


def test_repeat_import_corrections_and_metadata(engine, tmp_path):
    path = tmp_path / "prices.parquet"
    parquet(path, [row(), row(day=2), row("MSFT")])
    report = scan(path)
    assert import_snapshot(engine, path, report) == {"AAPL": 2, "MSFT": 1}
    import_snapshot(engine, path, report)
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(DailyBar)) == 3
        extras = connection.scalar(select(DailyBar.source_values).limit(1))
        assert extras["adj_close"] == 8.5
        assert extras["dividends"] == 0.25
    # An invalidated old observation must be removed, not retained as stale data.
    parquet(path, [row(close=10.5), row(day=2, volume=None), row("MSFT")])
    import_snapshot(engine, path, scan(path))
    history = database_history(engine, "AAPL", "all")
    assert len(history.bars) == 1
    assert history.bars[0].close == 10.5
    assert history.mode == "historical_snapshot"
    assert "Yahoo Finance" in history.source
    assert "unverified" in history.adjustment
    assert [stock.symbol for stock in search_database(engine, "")] == ["AAPL", "MSFT"]


def test_fixture_conflict_requires_explicit_replacement(engine, tmp_path):
    seed_fixture(engine)
    path = tmp_path / "prices.parquet"
    parquet(path, [row(), row("MSFT")])
    report = scan(path)
    with pytest.raises(ValueError, match="conflict"):
        import_snapshot(engine, path, report)
    assert len(database_history(engine, "AAPL", "all").bars) == 506
    assert search_database(engine, "MSFT") == []
    import_snapshot(engine, path, report, replace_existing=True)
    assert len(database_history(engine, "AAPL", "all").bars) == 1


def test_failed_symbol_transaction_restores_previous_snapshot(engine, tmp_path):
    path = tmp_path / "prices.parquet"
    parquet(path, [row()])
    report = scan(path)
    import_snapshot(engine, path, report)
    _, bar, _ = validated_row(row(close=10.5))
    bar["volume"] = -1
    with pytest.raises(IntegrityError):
        write_symbol(engine, "AAPL", [bar], report["sha256"])
    assert database_history(engine, "AAPL", "all").bars[0].close == 10.0


def test_duplicate_keys_and_changed_hash_are_rejected(engine, tmp_path):
    path = tmp_path / "prices.parquet"
    parquet(path, [row(), row()])
    with pytest.raises(ValueError, match="Duplicate"):
        scan(path)
    parquet(path, [row()])
    report = scan(path)
    parquet(path, [row(volume=50)])
    with pytest.raises(ValueError, match="hash"):
        import_snapshot(engine, path, report)
    assert search_database(engine, "") == []


def test_subset_and_rounding_validation(tmp_path):
    path = tmp_path / "prices.parquet"
    parquet(path, [row(), row("MSFT")])
    assert scan(path, {"MSFT"})["accepted_by_symbol"] == {"MSFT": 1}
    with pytest.raises(ValueError, match="No input"):
        scan(path, {"UNKNOWN"})
    _, _, reasons = validated_row(
        row(low=0.00000001, open=0.00000002, close=0.00000003)
    )
    assert "rounded_bounds" in reasons
