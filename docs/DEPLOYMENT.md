# Deployment plan

Nothing is deployed. Hosting, budget, domain, and production configuration remain undecided. GitHub Actions validates code; it does not publish services.

The frontend production bundle is generated with `npm ci` and `npm run build` in `frontend/`. A future static host can publish `frontend/dist/`; do not commit that directory. Vite's dev and preview servers are local tools, not the production hosting plan.

The API can run from `backend/` after installing `requirements.txt` with `python -m uvicorn app.main:app --host 0.0.0.0 --port 8000` behind a production host's HTTPS proxy. The host must control network exposure, process restarts, logging, and secret storage. Verify `/api/health` after deployment.

Before deployment, choose frontend/API origins and configure CORS only if needed. Before persistence is added, decide managed PostgreSQL, migrations, backups, and rollback. Before inference is added, define artifact storage and model loading. None of these integrations are part of Phase 0.
