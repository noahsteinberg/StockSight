# Integration adversarial review — November 16, 2026

Historical review evidence for the scope/date below, not a current startup or
completion checklist. See [current handoff](../CURRENT_HANDOFF.md) for resolved
runtime/import/session limitations, implemented indicators and remaining gates.
A later implementation does not retroactively change this review's original result.

Scope: local startup, environment selection, readiness, storage failure handling,
fixture/database boundaries, search/chart integration and verification claims.

## Findings

| Priority | Finding and evidence | Resolution |
| --- | --- | --- |
| P1 | Screenshot proves API startup succeeds but stock requests return 503. Saved configuration selects PostgreSQL; running Uvicorn alone does not start Docker, migrate or import prices. | Added LOCAL_START.md with explicit database prerequisites and a separate offline demo command. The live PostgreSQL cause is still unresolved. |
| P1 | Frontend says to check whether the API is running even when it receives a 503 response from that API. | Added distinct price-storage messages for 503 in search/history. |
| P1 | Readiness previously checked one column of daily_bars. Empty storage or missing/incompatible stocks/price_series tables could pass. | Readiness now checks all mapped market tables/columns and usable joined history. Added missing/partial/empty/schema-drift regression checks. |
| P2 | Every database read failure hides its cause. Public sanitization is correct, but local developers have no safe diagnosis command. | Added read-only app.doctor and safe codes for missing schema/data/database, authentication rejection and general storage failures. No raw exception or URL is printed. |
| P2 | Demo startup advice depends on overriding an existing database setting. Ordinary app import also constructs the configured engine before an explicit demo factory could ignore it. | Moved the app factory into its own module. app.demo:create_demo_app explicitly ignores even an invalid database URL; normal app.main behavior stays database-backed when configured. |
| P1 gate | Build success and focused tests cannot prove localhost reachability, the running database or browser integration. | Keep runtime signoff open. No claim that the current full browser/PostgreSQL flow passes. |

404 at port 8000 `/` or `/favicon.ico` is expected for an API-only server. The
website is port 5173; API documentation is `/docs`. Those 404s do not explain the
503 on stock history.

## Evidence and limits

- Local root/backend environment files exist. The saved PostgreSQL host is
  127.0.0.1, port 5433; saved passwords agree. Values were compared without
  revealing them. This does not establish the live role password or shell overrides.
- Docker command access from the agent session remains permission-denied.
  Do not infer whether the user's PostgreSQL container is running from that error.
- Fourteen targeted backend checks pass: new storage diagnostics and existing
  migration, import rollback, constraints, adapter parity and history-cap cases.
- Backend Ruff lint/format, frontend ESLint and production build pass.
- All 11 Playwright tests are discoverable. They have not been executed successfully
  for this change because the agent's local socket setup is blocked.
- No data, credentials, volumes or tables were reset by this review. Temporary
  SQLite databases belong only to the tests. No silent fallback was introduced.
- New review fixes remain local pending user review; no merge or publication
  success is claimed.

## Remaining acceptance checks

Run [local startup](../LOCAL_START.md) in normal terminals. Verify the explicit
demo chart first. Then diagnose and start PostgreSQL, migrate/import explicitly,
and confirm `/api/ready` reports database before the database-backed walkthrough.
Run the full pytest and Playwright suites against a disposable test database.
Record the exact commit and results before demo signoff.
