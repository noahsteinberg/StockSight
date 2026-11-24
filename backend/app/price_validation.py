"""Shared snapshot and provider-row validation; no implicit repairs."""

import math
import re
from datetime import datetime
from decimal import ROUND_HALF_EVEN, Decimal

PRICES = ("open", "high", "low", "close")


def validated_row(row):
    symbol, stamp = row["ticker"], row["date"]
    if not isinstance(symbol, str) or not re.fullmatch(
        r"[A-Z][A-Z0-9.\^=\-]{0,15}", symbol
    ):
        raise ValueError("Invalid or unnormalized ticker; validation stopped")
    if not isinstance(stamp, datetime) or stamp.tzinfo is not None:
        raise ValueError("Invalid trading-session timestamp; validation stopped")
    if any((stamp.hour, stamp.minute, stamp.second, stamp.microsecond)):
        raise ValueError("Non-midnight timestamp needs an explicit date policy")
    key = (symbol, stamp.date())
    reasons = []
    if row["bad_bar"] is not False:
        reasons.append("flagged_bar")
    numeric = (*PRICES, "adj_close", "volume", "dividends", "stock_splits")
    if any(row[name] is None for name in numeric):
        reasons.append("missing_value")
        return key, None, reasons
    if any(not math.isfinite(row[name]) for name in numeric):
        reasons.append("nonfinite_value")
        return key, None, reasons
    if any(row[name] <= 0 for name in (*PRICES, "adj_close")):
        reasons.append("nonpositive_price")
    if (
        row["low"] > row["high"]
        or not row["low"] <= row["open"] <= row["high"]
        or not row["low"] <= row["close"] <= row["high"]
    ):
        reasons.append("ohlc_bounds")
    if not isinstance(row["volume"], int) or not 0 <= row["volume"] <= 2**63 - 1:
        reasons.append("invalid_volume")
    if any(abs(row[name]) >= 1e12 for name in PRICES):
        reasons.append("numeric_overflow")
        return key, None, reasons
    rounded = {
        name: Decimal(str(row[name])).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_EVEN
        )
        for name in PRICES
    }
    if any(value >= Decimal("1000000000000") for value in rounded.values()):
        reasons.append("numeric_overflow")
    if (
        rounded["low"] <= 0
        or not rounded["low"] <= rounded["open"] <= rounded["high"]
        or not rounded["low"] <= rounded["close"] <= rounded["high"]
    ):
        reasons.append("rounded_bounds")
    if reasons:
        return key, None, reasons
    return (
        key,
        {
            "session_date": key[1],
            **rounded,
            "volume": row["volume"],
            "source_values": {
                name: row[name]
                for name in ("adj_close", "dividends", "stock_splits", "bad_bar")
            },
        },
        [],
    )
