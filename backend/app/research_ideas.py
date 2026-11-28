"""Bounded, descriptive research candidates from completed stored sessions."""

from datetime import date
from math import isfinite
from statistics import stdev
from typing import Literal

from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session, aliased

from app.db import DailyBar, PriceSeries, StockRecord, series_revision
from app.explore import _matches
from app.market import fixture_snapshot_id, load_bars
from app.patterns import recorded_event
from app.stock_metadata import company_name, profile_for, symbols_in_sector

IdeaMethod = Literal["momentum", "variability"]


class ResearchIdea(BaseModel):
    symbol: str
    name: str
    sector: str | None
    metric_pct: float
    as_of: date
    series_revision: str
    reason: str


class ResearchIdeas(BaseModel):
    calculation_version: Literal["research-ideas-v1"] = "research-ideas-v1"
    method: IdeaMethod
    query: str
    sectors: list[str]
    latest_session: date | None
    matching_count: int
    eligible_count: int
    page: int = 1
    page_size: int = 6
    items: list[ResearchIdea]


def metric(closes, events, method):
    if (
        len(closes) != 21
        or any(not isfinite(value) or value <= 0 for value in closes)
        or any(events)
    ):
        return None
    if method == "momentum":
        return 100 * (closes[-1] / closes[0] - 1)
    return stdev(100 * (b / a - 1) for a, b in zip(closes, closes[1:], strict=False))


def make_ideas(groups, latest, query, sectors, method, page=1):
    items = []
    for symbol, name, revision, bars in groups:
        if not bars or bars[-1][0] != latest:
            continue
        value = metric([bar[1] for bar in bars], [bar[2] for bar in bars], method)
        if value is None:
            continue
        profile = profile_for(symbol)
        reason = (
            f"{value:+.2f}% price change over the last 20 stored sessions."
            if method == "momentum"
            else f"{value:.2f}% daily variability over the last 20 stored changes."
        )
        items.append(
            ResearchIdea(
                symbol=symbol,
                name=company_name(symbol, name) or name,
                sector=profile.sector if profile else None,
                metric_pct=value,
                as_of=latest,
                series_revision=revision,
                reason=reason,
            )
        )
    items.sort(
        key=lambda item: (
            -item.metric_pct if method == "momentum" else item.metric_pct,
            item.symbol,
        )
    )
    return ResearchIdeas(
        method=method,
        query=query,
        sectors=sectors,
        latest_session=latest,
        matching_count=len(groups),
        eligible_count=len(items),
        page=page,
        items=items[(page - 1) * 6 : page * 6],
    )


def research_ideas(engine, query, sectors, method, *, private=False, page=1):
    if engine is None:
        profile = profile_for("AAPL")
        bars = load_bars()
        matches = (not query or query in "AAPL APPLE INC.") and (
            not sectors or profile.sector in sectors
        )
        groups = (
            [
                (
                    "AAPL",
                    "Apple Inc.",
                    fixture_snapshot_id(),
                    [(bar.date, bar.close, False) for bar in bars[-21:]],
                )
            ]
            if matches and not (private and not sectors)
            else []
        )
        return make_ideas(groups, bars[-1].date, query, sectors, method, page)
    recent = aliased(DailyBar)
    lower_bound = (
        select(recent.session_date)
        .where(recent.series_id == PriceSeries.id)
        .order_by(recent.session_date.desc())
        .offset(20)
        .limit(1)
        .correlate(PriceSeries)
        .scalar_subquery()
    )
    statement = (
        select(
            PriceSeries,
            StockRecord.name,
            DailyBar.session_date,
            DailyBar.close,
            DailyBar.source_values,
        )
        .select_from(PriceSeries)
        .join(StockRecord, StockRecord.symbol == PriceSeries.symbol)
        .join(
            DailyBar,
            and_(
                DailyBar.series_id == PriceSeries.id,
                DailyBar.session_date >= func.coalesce(lower_bound, date.min),
            ),
        )
        .order_by(PriceSeries.symbol, DailyBar.session_date)
    )
    if query:
        statement = statement.where(_matches(query))
    if sectors or private:
        allowed = [s for sector in sectors for s in symbols_in_sector(sector)]
        statement = statement.where(PriceSeries.symbol.in_(allowed))
    with Session(engine) as session:
        # One repeatable-read statement includes the universe cutoff and metadata.
        statement = statement.add_columns(
            select(func.max(DailyBar.session_date))
            .correlate(None)
            .scalar_subquery()
            .label("latest")
        )
        rows = session.execute(statement).all()
        latest = (
            rows[0].latest
            if rows
            else session.scalar(select(func.max(DailyBar.session_date)))
        )
        grouped = {}
        for row in rows:
            series, name = row[0], row[1]
            if series.symbol not in grouped:
                grouped[series.symbol] = (
                    series.symbol,
                    name,
                    series_revision(series),
                    [],
                )
            grouped[series.symbol][3].append(
                (row.session_date, float(row.close), recorded_event(row.source_values))
            )
    return make_ideas(list(grouped.values()), latest, query, sectors, method, page)
