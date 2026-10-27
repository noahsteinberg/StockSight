# Database direction

No database is configured or connected. PostgreSQL is the intended database; SQLAlchemy and Alembic are likely tools to evaluate in Phase 1. No schema, migrations, database driver, or connection string is included.

Candidate entities:

- Users: identity and account metadata
- Watchlists and entries: user ownership and selected stocks
- Stocks and cached market data: symbol, exchange, timestamp, OHLCV, interval, source, adjustment policy
- Predictions: model version, stock, creation/cutoff time, horizon, output, eventual observed outcome
- Model versions and evaluation results: feature schema, training window, artifact reference, metrics, baseline

Before migration work, agree on keys, constraints, deletion/retention, timezone and trading-date semantics, and cache freshness. Prevent duplicate bars with a deliberate uniqueness key. Parameterize queries and enforce ownership on the backend. Use isolated test data and keep migrations reproducible.
