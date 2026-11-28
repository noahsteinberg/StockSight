"""Check the faster offline scorer against application logic and future changes."""

from datetime import date, timedelta

import numpy as np

from app.evaluate_patterns import feature_matrix, score_at
from app.patterns import PatternBar, calculate_patterns


def test_offline_scorer_matches_app_and_ignores_future_values():
    index = np.arange(700)
    closes = 100 * np.exp(0.0004 * index + 0.04 * np.sin(index / 17))
    raw_events = np.zeros(700, dtype=int)
    raw_events[110] = 1
    events = np.r_[0, np.cumsum(raw_events)]
    indices, features = feature_matrix(closes)
    for cutoff in (400, 550):
        scored = score_at(closes, events, indices, features, cutoff)
        bars = [
            PatternBar(
                date(2015, 1, 1) + timedelta(days=int(i)),
                float(closes[i]),
                bool(raw_events[i]),
            )
            for i in range(cutoff + 1)
        ]
        exact = calculate_patterns(
            bars,
            21,
            symbol="TEST",
            name="Synthetic",
            snapshot_id="test",
            source="test",
            source_url="https://example.test",
            adjustment="test",
            has_earlier=False,
        )
        assert exact.status == "available"
        assert abs(scored[0] - exact.summary.median_change_pct) < 1e-7
        later = closes.copy()
        later[cutoff + 1 :] *= 20
        updated_indices, updated_features = feature_matrix(later)
        assert scored == score_at(
            later, events, updated_indices, updated_features, cutoff
        )
