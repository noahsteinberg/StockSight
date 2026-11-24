"""Plan and atomically apply incremental daily updates. No provider calls in APIs."""

import json
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import (
    DailyBar,
    MarketBarChange,
    MarketRefreshRun,
    PriceSeries,
    series_revision,
)
from app.price_validation import PRICES, validated_row

FIELDS = (*PRICES, "volume")
SERIES_FIELDS = ("source", "source_url", "mode", "adjustment", "updated_at")
RETAIN = 2500


def json_value(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def serialize(value):
    return json.loads(json.dumps(value, default=json_value, sort_keys=True))


def revision(series):
    return series_revision(series)


def bar_values(bar):
    return serialize(
        {
            **{field: getattr(bar, field) for field in FIELDS},
            "source_values": deepcopy(bar.source_values),
        }
    )


@dataclass
class Snapshot:
    series_id: str
    symbol: str
    revision: str
    bars: dict
    metadata: dict


def read_snapshot(engine, symbol):
    # One statement, like chart reads, binds the bars to their series revision.
    with Session(engine) as session:
        rows = session.execute(
            select(PriceSeries, DailyBar)
            .join(DailyBar, DailyBar.series_id == PriceSeries.id)
            .where(PriceSeries.symbol == symbol)
            .order_by(DailyBar.session_date)
        ).all()
        if not rows:
            raise ValueError("Unsupported symbol or no stored history")
        series = rows[0][0]
        if series.mode == "historical_fixture":
            raise ValueError(
                "Refresh requires an imported team series, not a demo fixture"
            )
        if not series.id.startswith("team-yahoo-v1-"):
            raise ValueError("Unverified initial provider series")
        return Snapshot(
            series.id,
            symbol,
            revision(series),
            {bar.session_date: bar_values(bar) for _, bar in rows},
            serialize({field: getattr(series, field) for field in SERIES_FIELDS}),
        )


@dataclass
class RefreshPlan:
    snapshot: Snapshot
    provider: str
    fingerprint: str
    fetched_at: datetime
    start: date
    end: date
    updates: dict
    rejected: list
    missing: list
    blockers: list
    adjusted_changes: list
    unchanged: int

    def report(self):
        proposed_dates = sorted(set(self.snapshot.bars) | set(self.updates))
        removed = proposed_dates[: max(0, len(proposed_dates) - RETAIN)]
        return serialize(
            {
                "symbol": self.snapshot.symbol,
                "base_revision": self.snapshot.revision,
                "stored_cutoff": max(self.snapshot.bars),
                "requested_start": self.start,
                "requested_end": self.end,
                "provider": self.provider,
                "provider_options": {
                    "interval": "1d",
                    "auto_adjust": False,
                    "back_adjust": False,
                    "repair": False,
                    "actions": True,
                    "keepna": True,
                    "calendar": "XNYS",
                    "finalization_buffer_minutes": 30,
                },
                "fingerprint": self.fingerprint,
                "fetched_at": self.fetched_at,
                "inserts": [
                    day for day in self.updates if day not in self.snapshot.bars
                ],
                "corrections": [
                    {"date": day, "before": self.snapshot.bars[day], "after": values}
                    for day, values in self.updates.items()
                    if day in self.snapshot.bars
                ],
                "unchanged": self.unchanged,
                "rejected": self.rejected,
                "missing_sessions": self.missing,
                "blockers": self.blockers,
                "adjusted_close_observations": self.adjusted_changes,
                "retention_removals": removed,
                "retained_bars": len(proposed_dates) - len(removed),
            }
        )


def plan_refresh(snapshot, download, start, end, completed):
    """Reuse the import validator; never fill gaps or repair incompatible prices."""
    cutoff = max(snapshot.bars)
    overlap = set(sorted(snapshot.bars)[-20:])
    blockers, rejected, adjusted_changes = [], [], []
    candidates, returned = {}, set()
    unchanged = 0
    previous = None
    for incoming in download.rows:
        try:
            day = date.fromisoformat(incoming["date"])
        except (KeyError, TypeError, ValueError):
            blockers.append("Invalid provider date")
            continue
        if incoming.get("ticker") != snapshot.symbol or not start <= day <= end:
            blockers.append("Unexpected provider symbol/date")
            continue
        if previous is not None and day <= previous:
            blockers.append("Duplicate or unordered provider dates")
            continue
        previous = day
        returned.add(day)
        if day not in completed:
            rejected.append({"date": day, "reasons": ["session_not_finalized"]})
            continue
        # bad_bar=False means our validator sees no upstream bad-bar flag; it
        # does not assert that Yahoo independently certified this bar as clean.
        row = {
            **incoming,
            "date": datetime.combine(day, datetime.min.time()),
            "bad_bar": False,
        }
        try:
            _, accepted, reasons = validated_row(row)
        except (ValueError, TypeError, KeyError, OverflowError):
            accepted, reasons = None, ["malformed_provider_row"]
        if accepted is None:
            rejected.append({"date": day, "reasons": reasons})
            if day in overlap:
                blockers.append("Invalid overlapping provider bar")
            continue
        values = serialize(
            {field: accepted[field] for field in (*FIELDS, "source_values")}
        )
        old = snapshot.bars.get(day)
        if accepted["source_values"]["stock_splits"]:
            blockers.append(
                "Split event requires a separately reviewed history rebuild"
            )
        if old:
            if any(values[field] != old[field] for field in PRICES):
                blockers.append("Overlapping OHLC differs; review provider price basis")
                continue
            fresh_adj = values["source_values"].get("adj_close")
            old_adj = (old["source_values"] or {}).get("adj_close")
            if old_adj != fresh_adj:
                adjusted_changes.append(
                    {"date": day, "before": old_adj, "observed": fresh_adj}
                )
            # Preserve old adjusted-close vintage/actions on overlap. Observed
            # retrospective changes belong to the refresh record, not chart OHLC.
            values["source_values"] = deepcopy(old["source_values"])
            if values["volume"] != old["volume"]:
                candidates[day] = values
            else:
                unchanged += 1
        else:
            if day <= cutoff:
                blockers.append(
                    "Provider returned a previously absent historical session"
                )
            else:
                candidates[day] = values
    if overlap - returned:
        blockers.append("Provider omitted stored overlap sessions")
    expected_new = {day for day in completed if cutoff < day <= end}
    valid_new = {day for day in candidates if day > cutoff}
    missing = sorted(expected_new - valid_new)
    # Do not advance past a missing session: the next run must retry the gap.
    if missing:
        candidates = {
            day: value for day, value in candidates.items() if day < missing[0]
        }
    if blockers:
        candidates = {}
    return RefreshPlan(
        snapshot,
        download.provider,
        download.fingerprint,
        download.fetched_at,
        start,
        end,
        candidates,
        rejected,
        missing,
        sorted(set(blockers)),
        adjusted_changes,
        unchanged,
    )


def _restore_values(values):
    from decimal import Decimal

    return {
        **values,
        **{field: Decimal(values[field]) for field in PRICES},
        "volume": int(values["volume"]),
    }


def apply_refresh(engine, plan):
    if plan.blockers:
        raise ValueError("Refresh blocked; inspect dry-run report")
    run_id = str(uuid4())
    report = plan.report()
    with Session(engine) as session, session.begin():
        series = session.scalar(
            select(PriceSeries)
            .where(PriceSeries.id == plan.snapshot.series_id)
            .with_for_update()
        )
        if series is None or revision(series) != plan.snapshot.revision:
            raise ValueError("Series changed since preview; fetch and preview again")
        # Ensure a new ORM read did not hide an unexpected direct bar mutation.
        actual = {
            bar.session_date: bar_values(bar)
            for bar in session.scalars(
                select(DailyBar).where(DailyBar.series_id == series.id)
            )
        }
        if actual != plan.snapshot.bars:
            raise ValueError("Stored bars changed since preview")
        run = MarketRefreshRun(
            id=run_id,
            series_id=series.id,
            started_at=plan.fetched_at,
            status="partial" if plan.missing else "success",
            provider=plan.provider,
            fingerprint=plan.fingerprint,
            details={**report, "before_series": plan.snapshot.metadata},
            applied_revision=None,
        )
        session.add(run)
        session.flush()
        changes = {}
        for day, values in plan.updates.items():
            before = actual.get(day)
            data = _restore_values(values)
            data["source_values"] = {
                **(data["source_values"] or {}),
                "refresh_run_id": run_id,
            }
            existing = session.get(DailyBar, (series.id, day))
            if existing:
                for field, value in data.items():
                    setattr(existing, field, value)
            else:
                session.add(DailyBar(series_id=series.id, session_date=day, **data))
            after = serialize(data)
            actual[day] = after
            changes[day] = [before, after]
        for day in sorted(actual)[: max(0, len(actual) - RETAIN)]:
            before = actual.pop(day)
            session.execute(
                delete(DailyBar).where(
                    DailyBar.series_id == series.id, DailyBar.session_date == day
                )
            )
            # An inserted-then-trimmed row is not a durable change.
            original = changes.get(day, [before, None])[0]
            if original is None:
                changes.pop(day, None)
            else:
                changes[day] = [original, None]
        for day, (before, after) in changes.items():
            session.add(
                MarketBarChange(
                    run_id=run_id, session_date=day, before=before, after=after
                )
            )
        if changes:
            series.updated_at = datetime.now(UTC)
            series.mode = "daily_history"
            series.source = (
                "Yahoo Finance daily history "
                "(initial team snapshot plus validated updates)"
            )
            series.source_url = "https://finance.yahoo.com/"
            series.adjustment = (
                "Team/Yahoo OHLC; adjustment compatibility checked on recent overlap. "
                "Adjusted-close vintages retained separately. "
                "Latest 2500 valid sessions retained."
            )
            session.flush()
        run.applied_revision = revision(series)
        return {
            **report,
            "run_id": run_id,
            "status": run.status,
            "changed_bars": len(changes),
            "retained_bars": len(actual),
            "snapshot_id": run.applied_revision,
        }


def record_failure(engine, snapshot, error_type, start, end, *, details=None):
    """Write-mode failure journal; no bars or revision are changed."""
    run_id = str(uuid4())
    with Session(engine) as session, session.begin():
        session.add(
            MarketRefreshRun(
                id=run_id,
                series_id=snapshot.series_id,
                started_at=datetime.now(UTC),
                status="error",
                provider="yfinance",
                fingerprint=None,
                applied_revision=None,
                details={
                    **(details or {}),
                    "error_type": error_type,
                    "requested_start": start.isoformat(),
                    "requested_end": end.isoformat(),
                },
            )
        )
    return run_id


def restore_refresh(engine, run_id):
    """Undo only the most recent changed revision; never overwrite newer work."""
    with Session(engine) as session, session.begin():
        run = session.get(MarketRefreshRun, run_id)
        if not run or run.status == "rolled_back":
            raise ValueError("Unknown or already restored refresh")
        series = session.scalar(
            select(PriceSeries).where(PriceSeries.id == run.series_id).with_for_update()
        )
        if revision(series) != run.applied_revision:
            raise ValueError(
                "A newer series revision exists; automatic restore refused"
            )
        changes = list(
            session.scalars(
                select(MarketBarChange).where(MarketBarChange.run_id == run_id)
            )
        )
        for change in changes:
            bar = session.get(DailyBar, (series.id, change.session_date))
            actual = bar_values(bar) if bar else None
            if actual != change.after:
                raise ValueError("Stored bar changed since refresh; restore refused")
            if change.before is None:
                if bar:
                    session.delete(bar)
            else:
                values = _restore_values(change.before)
                if bar:
                    for field, value in values.items():
                        setattr(bar, field, value)
                else:
                    session.add(
                        DailyBar(
                            series_id=series.id,
                            session_date=change.session_date,
                            **values,
                        )
                    )
        if changes:
            for field, value in run.details["before_series"].items():
                if field != "updated_at":
                    setattr(series, field, value)
            series.updated_at = datetime.now(UTC)
        run.status = "rolled_back"
        return {
            "run_id": run_id,
            "status": "rolled_back",
            "restored_bars": len(changes),
        }
