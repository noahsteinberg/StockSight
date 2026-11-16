# Start and diagnose StockSight

Keep two PowerShell terminals open. Stop an existing service with Ctrl+C in its
own terminal before restarting it. The website is on port 5173; port 8000 is the
API. A 404 for the API's `/` or favicon is expected.

## Explicit demo without PostgreSQL

From the repository root, terminal 1:

```powershell
cd backend
.\.venv\Scripts\python.exe -m uvicorn app.demo:create_demo_app --factory --host 127.0.0.1 --port 8000
```

From the repository root, terminal 2:

```powershell
cd frontend
npm run dev
```

Open http://127.0.0.1:5173. This explicit demo factory ignores saved database
configuration without editing it. It serves 506 historical AAPL observations;
it does not verify PostgreSQL. `/api/ready` reports storage fixture.
Use the existing installed dependencies; see README for fresh installation.

## PostgreSQL integration

Start Docker Desktop, then from the repository root:

```powershell
docker compose up -d --wait
cd backend
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m app.seed
.\.venv\Scripts\python.exe -m app.doctor
```

Stop if any command fails. With `Storage ready: database`, start the regular API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Run the frontend in terminal 2 as above. `/api/ready` must report storage database.
Root `.env` configures Compose; `backend/.env` configures FastAPI. The database URL
uses local port 5433. A shell variable can override the saved backend value.
Changing `.env` does not change a password in an existing PostgreSQL volume.
Do not delete the volume to troubleshoot or paste credentials into reports.

## Diagnostic results

The doctor command is read-only and exits nonzero on failure. It never changes
schema, imports data, drops tables, switches storage modes, or prints raw errors.

| Code or symptom | Meaning | Recovery |
| --- | --- | --- |
| 503 on stock routes | API answered; storage query failed | Run app.doctor |
| SCHEMA_MISSING | Required tables absent | alembic upgrade head |
| DATA_NOT_IMPORTED | No usable stored history | Explicit app.seed for the agreed fixture |
| DATABASE_AUTH_FAILED | PostgreSQL rejected login | Check existing role credentials |
| DATABASE_MISSING | Configured database absent | Check database name and Compose setup |
| STORAGE_UNAVAILABLE | Connection/query/schema unavailable | Check Docker, port, settings, migrations |
| Browser connection refused | Frontend listener unreachable | Start npm run dev in your own terminal |

Startup complete and `/api/health` prove process health only. `/api/ready` now
checks all market tables and requires usable joined history in database mode.
Database failure never silently falls back to demo data.
