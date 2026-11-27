"""Bounded, descriptive historical analogs. No forecasts or provider calls."""

from dataclasses import dataclass
from datetime import date
from math import fsum, isfinite, sqrt
from statistics import fmean, stdev
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from app.db import DailyBar, PriceSeries, StockRecord, series_revision
from app.market import ADJUSTMENT, SOURCE, SOURCE_URL, fixture_snapshot_id, load_bars
from app.stock_metadata import company_name

LIMIT = 2500
LOOKBACK = 50
MATCH_LIMIT = 12
MIN_MATCHES = 8
HORIZONS = (5, 21)


class Setup(BaseModel):
    change_20_pct: float
    daily_variability_pct: float
    vs_average_50_pct: float


class PatternMatch(BaseModel):
    date: date
    end_date: date
    setup: Setup
    change_pct: float
    path: list[float]


class PatternPoint(BaseModel):
    session: int
    lower_quartile: float
    median: float
    upper_quartile: float


class PatternSummary(BaseModel):
    median_change_pct: float
    lower_quartile_pct: float
    upper_quartile_pct: float
    rose: int
    fell: int
    unchanged: int


class PatternResponse(BaseModel):
    methodology: Literal["historical-price-patterns-v1"] = (
        "historical-price-patterns-v1"
    )
    symbol: str
    name: str
    as_of: date
    snapshot_id: str
    source: str
    source_url: str
    adjustment: str
    horizon_sessions: Literal[5, 21]
    status: Literal["available", "unavailable"]
    reason: (
        Literal["insufficient_history", "insufficient_matches", "invalid_history"]
        | None
    )
    current_setup: Setup | None
    calculation_start: date
    calculation_sessions: int
    has_earlier: bool
    eligible_candidates: int = 0
    excluded_event_windows: int = 0
    matched_count: int = 0
    summary: PatternSummary | None = None
    points: list[PatternPoint] = []
    matches: list[PatternMatch] = []


@dataclass(frozen=True)
class PatternBar:
    date: date
    close: float
    # Exclude all recorded split/distribution events, including ambiguous ratios.
    event: bool = False


def percentile(values: list[float], quantile: float) -> float:
    """Linear interpolation on sorted observations; not a forecast interval."""
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def setup_at(bars: list[PatternBar], index: int) -> Setup:
    """Trailing state at t uses t-49..t only; returns use 21 closes."""
    closes = [bar.close for bar in bars[index - 49 : index + 1]]
    changes = [
        100 * (b / a - 1) for a, b in zip(closes[-21:-1], closes[-20:], strict=True)
    ]
    return Setup(
        change_20_pct=100 * (closes[-1] / closes[-21] - 1),
        daily_variability_pct=stdev(changes),
        vs_average_50_pct=100 * (closes[-1] / fmean(closes) - 1),
    )


def vector(setup: Setup) -> tuple[float, float, float]:
    return (setup.change_20_pct, setup.daily_variability_pct, setup.vs_average_50_pct)


def choose_matches(candidates, current: Setup, horizon: int):
    """Order by feature distance only. Outcome returns never enter selection.

    Scales use eligible historical setup values at this query cutoff. This is
    descriptive retrieval, not an out-of-sample forecasting evaluation.
    """
    current_values = vector(current)
    columns = list(zip(*(vector(state) for _, state in candidates), strict=True))
    scales = [stdev(column) if len(column) > 1 else 0.0 for column in columns]
    # A constant historical feature cannot create arbitrary huge distances.
    active = [i for i, scale in enumerate(scales) if scale > 1e-12]
    if not active:
        return []
    ordered = sorted(
        candidates,
        key=lambda item: (
            sqrt(
                fsum(
                    ((vector(item[1])[i] - current_values[i]) / scales[i]) ** 2
                    for i in active
                )
            ),
            item[0],
        ),
    )
    selected = []
    for item in ordered:
        # Outcome paths, including endpoints, cannot share stored observations.
        if all(abs(item[0] - previous[0]) > horizon for previous in selected):
            selected.append(item)
        if len(selected) == MATCH_LIMIT:
            break
    return selected


def calculate_patterns(
    bars: list[PatternBar], horizon: int, **metadata
) -> PatternResponse:
    if horizon not in HORIZONS:
        raise ValueError("Unsupported pattern horizon")
    if not bars:
        raise ValueError("Pattern history is empty")
    result = PatternResponse(
        **metadata,
        horizon_sessions=horizon,
        as_of=bars[-1].date,
        calculation_start=bars[0].date,
        calculation_sessions=len(bars),
        status="unavailable",
        reason="insufficient_history",
        current_setup=None,
    )
    if any(not isfinite(bar.close) or bar.close <= 0 for bar in bars) or any(
        a.date >= b.date for a, b in zip(bars, bars[1:], strict=False)
    ):
        return result.model_copy(update={"reason": "invalid_history"})
    if len(bars) < LOOKBACK + horizon + MIN_MATCHES:
        return result
    # Current state crossing a recorded event is not presented as comparable.
    if any(bar.event for bar in bars[-LOOKBACK:]):
        return result.model_copy(update={"reason": "insufficient_matches"})
    current = setup_at(bars, len(bars) - 1)
    candidates, excluded = [], 0
    for index in range(LOOKBACK - 1, len(bars) - horizon):
        if any(bar.event for bar in bars[index - 49 : index + horizon + 1]):
            excluded += 1
            continue
        candidates.append((index, setup_at(bars, index)))
    result = result.model_copy(
        update={
            "current_setup": current,
            "eligible_candidates": len(candidates),
            "excluded_event_windows": excluded,
            "reason": "insufficient_matches",
        }
    )
    if not candidates:
        return result
    selected = choose_matches(candidates, current, horizon)
    if len(selected) < MIN_MATCHES:
        return result
    matches = []
    for index, state in selected:
        path = [
            100 * (bar.close / bars[index].close - 1)
            for bar in bars[index : index + horizon + 1]
        ]
        matches.append(
            PatternMatch(
                date=bars[index].date,
                end_date=bars[index + horizon].date,
                setup=state,
                change_pct=path[-1],
                path=path,
            )
        )
    outcomes = [match.change_pct for match in matches]
    points = [
        PatternPoint(
            session=i,
            lower_quartile=percentile([m.path[i] for m in matches], 0.25),
            median=percentile([m.path[i] for m in matches], 0.5),
            upper_quartile=percentile([m.path[i] for m in matches], 0.75),
        )
        for i in range(horizon + 1)
    ]
    return result.model_copy(
        update={
            "status": "available",
            "reason": None,
            "matched_count": len(matches),
            "matches": matches,
            "points": points,
            "summary": PatternSummary(
                median_change_pct=percentile(outcomes, 0.5),
                lower_quartile_pct=percentile(outcomes, 0.25),
                upper_quartile_pct=percentile(outcomes, 0.75),
                rose=sum(value > 0 for value in outcomes),
                fell=sum(value < 0 for value in outcomes),
                unchanged=sum(value == 0 for value in outcomes),
            ),
        }
    )


def recorded_event(values) -> bool:
    try:
        ratio = float((values or {}).get("stock_splits") or 0)
        return not isfinite(ratio) or ratio not in (0, 1)
    except (TypeError, ValueError):
        return True


def patterns_database(
    engine: Engine, symbol: str, horizon: int
) -> PatternResponse | None:
    with Session(engine) as session:
        # One statement ties the complete calculation to one committed revision.
        rows = session.execute(
            select(PriceSeries, StockRecord.name, DailyBar)
            .select_from(PriceSeries)
            .join(StockRecord, StockRecord.symbol == PriceSeries.symbol)
            .join(DailyBar, DailyBar.series_id == PriceSeries.id)
            .where(PriceSeries.symbol == symbol)
            .order_by(DailyBar.session_date.desc())
            .limit(LIMIT + 1)
        ).all()
        if not rows:
            return None
        series, name, _ = rows[0]
        metadata = dict(
            symbol=symbol,
            name=company_name(symbol, name) or name,
            source=series.source,
            source_url=series.source_url,
            adjustment=series.adjustment,
            snapshot_id=series_revision(series),
            has_earlier=len(rows) > LIMIT,
        )
        bars = [
            PatternBar(
                row.session_date, float(row.close), recorded_event(row.source_values)
            )
            for _, _, row in reversed(rows[:LIMIT])
        ]
    return calculate_patterns(bars, horizon, **metadata)


def patterns_fixture(horizon: int) -> PatternResponse:
    bars = [PatternBar(bar.date, bar.close) for bar in load_bars()]
    return calculate_patterns(
        bars,
        horizon,
        symbol="AAPL",
        name="Apple Inc.",
        source=SOURCE,
        source_url=SOURCE_URL,
        adjustment=ADJUSTMENT,
        snapshot_id=fixture_snapshot_id(),
        has_earlier=False,
    )
