# Database implementation

PostgreSQL persistence is implemented through Alembic revision
`0004_app_sessions`. Market tables are stocks, price_series and daily_bars;
private tables are user_identities, watchlist_entries and auth_sessions.
The validated snapshot importer and explicit fixture seed are separate commands.

Read [DATABASE.md](../docs/DATABASE.md) for schema, setup and disposable tests,
[PRICES_IMPORT.md](../docs/PRICES_IMPORT.md) for canonical-series replacement,
and [CURRENT_HANDOFF.md](../docs/CURRENT_HANDOFF.md) for current integration context.
Never seed/reset the existing imported database or commit source data/credentials.
