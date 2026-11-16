# StockSight working instructions

Before Docker commands, development-server startup or live HTTP/database tests,
run backend's virtual-environment Python with `-m app.environment_check` from
backend. This is a read-only execution-access check; see docs/ENVIRONMENT_ACCESS.md.

Distinguish permission_denied from not_running/not_listening. If access is denied,
do not repeatedly restart servers or scan/import the dataset to troubleshoot it.
Use the configured approval mechanism if available; otherwise report the precise
execution limitation and continue useful offline checks. Project code cannot
grant permissions withheld by the session runner. Never report a service reachable
solely because its process printed a ready message.

Use a unique subdirectory under backend/.pytest_cache as pytest --basetemp when
the sandbox's redirected temporary directory is inaccessible. Do not replace
integration tests with direct calls and then describe them as HTTP/browser tests.

Keep source datasets, credentials and local verification reports outside Git.
Use the explicit demo factory for offline fixture runs; do not silently fall back
from configured database reads. Import commands and replacement semantics are in
docs/PRICES_IMPORT.md. No screen capture is needed for normal backend operations.
