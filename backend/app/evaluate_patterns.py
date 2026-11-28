"""Offline development-only 21-session ranking diagnostic. Never exports a model."""

import argparse
import json
from collections import defaultdict
from datetime import datetime
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from app.import_prices import input_hash
from app.patterns import PatternBar, calculate_patterns, recorded_event
from app.price_validation import validated_row


def feature_matrix(closes):
    indices = np.arange(49, len(closes))
    returns = 100 * (closes[1:] / closes[:-1] - 1)
    values = np.column_stack(
        (
            100 * (closes[indices] / closes[indices - 20] - 1),
            np.lib.stride_tricks.sliding_window_view(returns, 20).std(axis=1, ddof=1)[
                29:
            ],
            100
            * (
                closes[indices]
                / np.lib.stride_tricks.sliding_window_view(closes, 50).mean(axis=1)
                - 1
            ),
        )
    )
    return indices, values


def score_at(closes, events, indices, features, t):
    start = max(0, t - 2499)
    if events[t + 1] - events[t - 49]:
        return None
    valid = (indices >= start + 49) & (indices <= t - 21)
    candidates = indices[valid]
    states = features[valid]
    clean = events[candidates + 22] == events[candidates - 49]
    candidates, states = candidates[clean], states[clean]
    if len(candidates) < 8:
        return None
    scale = states.std(axis=0, ddof=1)
    active = scale > 1e-12
    if not active.any():
        return None
    current = features[t - 49]
    distances = np.linalg.norm(
        (states[:, active] - current[active]) / scale[active], axis=1
    )
    ordered = np.lexsort((candidates, distances))
    selected, selected_distances = [], []
    for position in ordered:
        index = int(candidates[position])
        if all(abs(index - prior) > 21 for prior in selected):
            selected.append(index)
            selected_distances.append(float(distances[position]))
        if len(selected) == 12:
            break
    if len(selected) < 8:
        return None
    # Every candidate outcome was fully observed by t.
    outcomes = 100 * (closes[np.array(selected) + 21] / closes[selected] - 1)
    unconditional = 100 * (closes[candidates + 21] / closes[candidates] - 1)
    return (
        float(np.median(outcomes)),
        float(current[0]),
        float(np.median(unconditional)),
        float(np.mean(selected_distances)),
    )


def summarize(rows):
    frame = pd.DataFrame(rows)
    results = {}
    for method in ("patterns", "momentum", "unconditional"):
        dates, previous = [], None
        for day, group in frame.groupby("date", sort=True):
            ordered = group.sort_values([method, "symbol"], kind="stable")
            k = max(1, int(np.ceil(len(group) / 10)))
            top = set(ordered.tail(k).symbol)
            rank = group[method].rank().to_numpy()
            realized = group.outcome.rank().to_numpy()
            ic = (
                float(np.corrcoef(rank, realized)[0, 1])
                if rank.std() and realized.std()
                else None
            )
            spread = float(
                ordered.tail(k).outcome.mean() - ordered.head(k).outcome.mean()
            )
            dates.append(
                {
                    "date": day,
                    "stocks": len(group),
                    "rank_ic": ic,
                    "gross_decile_spread_pct": spread,
                    "illustrative_spread_after_40bps_pct": spread - 0.4,
                    "top_decile_turnover": None
                    if previous is None
                    else 1 - len(top & previous) / max(len(top), len(previous)),
                }
            )
            previous = top
        aggregate = pd.DataFrame(dates)
        results[method] = {
            "mean_rank_ic": float(aggregate.rank_ic.mean()),
            "mean_gross_decile_spread_pct": float(
                aggregate.gross_decile_spread_pct.mean()
            ),
            "mean_illustrative_spread_after_40bps_pct": float(
                aggregate.illustrative_spread_after_40bps_pct.mean()
            ),
            "mean_top_decile_turnover": float(aggregate.top_decile_turnover.mean()),
            "by_year": {
                year: {
                    "mean_rank_ic": float(block.rank_ic.mean()),
                    "mean_gross_decile_spread_pct": float(
                        block.gross_decile_spread_pct.mean()
                    ),
                }
                for year, block in aggregate.groupby(aggregate.date.str[:4])
            },
            "dates": dates,
        }
    return results


def run(path):
    # Push the cutoff into the reader. No 2019+ observation is loaded or scored.
    fingerprint = input_hash(path)
    table = pq.read_table(path, filters=[("date", "<=", datetime(2018, 12, 31))])
    grouped = defaultdict(list)
    rejected = 0
    previous = None
    for row in table.to_pylist():
        key, bar, _ = validated_row(row)
        if previous is not None and key <= previous:
            raise ValueError("Duplicate or out-of-order source")
        previous = key
        if bar:
            grouped[key[0]].append(bar)
        else:
            rejected += 1
    all_dates = sorted(
        {bar["session_date"] for bars in grouped.values() for bar in bars}
    )
    calendar = pd.Series(all_dates)
    months = calendar.groupby(calendar.map(lambda d: d.strftime("%Y-%m"))).last()
    cutoffs = [day for day in months if 2014 <= day.year <= 2018]
    rows, possible, parity_checks = [], 0, 0
    for symbol, bars in sorted(grouped.items()):
        if len(bars) < 100:
            continue
        dates = [bar["session_date"] for bar in bars]
        lookup = {day: i for i, day in enumerate(dates)}
        closes = np.array([float(bar["close"]) for bar in bars])
        raw_events = np.array([recorded_event(bar["source_values"]) for bar in bars])
        events = np.r_[0, np.cumsum(raw_events)]
        indices, features = feature_matrix(closes)
        for day in cutoffs:
            t = lookup.get(day)
            if t is None or t < 99 or t + 21 >= len(bars):
                continue
            possible += 1
            # Unrecorded actions remain a limitation; recorded future events
            # are excluded from outcomes and counted in the coverage denominator.
            if raw_events[t + 1 : t + 22].any():
                continue
            scored = score_at(closes, events, indices, features, t)
            if scored is None:
                continue
            pattern, momentum, unconditional, distance = scored
            if parity_checks < 6:
                window = bars[max(0, t - 2499) : t + 1]
                exact = calculate_patterns(
                    [
                        PatternBar(
                            b["session_date"],
                            float(b["close"]),
                            recorded_event(b["source_values"]),
                        )
                        for b in window
                    ],
                    21,
                    symbol=symbol,
                    name=symbol,
                    snapshot_id="offline-parity",
                    source="frozen team snapshot",
                    source_url="https://finance.yahoo.com/",
                    adjustment="unverified team OHLC",
                    has_earlier=t >= 2500,
                )
                assert exact.status == "available"
                assert abs(pattern - exact.summary.median_change_pct) < 1e-7
                assert (
                    abs(distance - np.mean([m.match_distance for m in exact.matches]))
                    < 1e-7
                )
                parity_checks += 1
            rows.append(
                {
                    "symbol": symbol,
                    "date": day.isoformat(),
                    "patterns": pattern,
                    "momentum": momentum,
                    "unconditional": unconditional,
                    "outcome": float(100 * (closes[t + 21] / closes[t] - 1)),
                    "distance": distance,
                }
            )
        print(f"{symbol}: cumulative {len(rows)} evaluated observations", flush=True)
    assert input_hash(path) == fingerprint
    if not rows:
        raise ValueError("No eligible development observations")
    return {
        "protocol": "historical-pattern-ranking-development-v1",
        "environment": {
            name: version(name)
            for name in ("numpy", "pandas", "pyarrow", "pydantic", "SQLAlchemy")
        },
        "source_sha256": fingerprint,
        "horizon_sessions": 21,
        "development_period": ["2014-01-01", "2018-12-31"],
        "parity_checks": parity_checks,
        "rejected_source_bars": rejected,
        "eligible_observations": len(rows),
        "possible_observations": possible,
        "coverage": len(rows) / possible,
        "stock_count": len(grouped),
        "mean_match_distance": float(np.mean([r["distance"] for r in rows])),
        "limitations": [
            "Current snapshot universe has survivorship bias.",
            "Price adjustment is unverified; price-only returns exclude dividends.",
            "Recorded corporate-action outcomes are excluded, conditioning coverage.",
            "Monthly 21-session outcomes can overlap and are not independent.",
            "Same-close diagnostic cannot establish executable next-entry returns.",
            "40bps is illustrative roundtrip long-short cost, not measured execution.",
            "This reused development period cannot approve a serving model.",
        ],
        "results": summarize(rows),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if args.output.exists() or args.source.resolve() == args.output.resolve():
        raise ValueError("Output must be a new file")
    report = run(args.source)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print(f"Saved aggregate report to {args.output}", flush=True)


if __name__ == "__main__":
    main()
