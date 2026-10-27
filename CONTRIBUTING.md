# Contributing

Team: Noah Steinberg, Gavin Javier Pino, Parth Sachdev, and Vladislav Lagutin.

## Workflow

1. Pull the latest `main`: `git switch main`, then `git pull --ff-only origin main`.
2. Create a branch: `git switch -c feature/watchlists`.
3. Make a focused change and update affected documentation.
4. Run frontend `npm run lint` and `npm run build` in `frontend/`; run Ruff check, Ruff format check, and pytest in `backend/` as shown in the README.
5. Review `git diff` and `git status`; commit with a clear description.
6. Push your branch: `git push -u origin feature/watchlists`.
7. Open a pull request using the template.
8. Ask a teammate to review; resolve comments and failing CI.
9. Merge after review and passing checks; delete the merged branch.

Other branch examples: `feature/stock-analysis`, `feature/prediction-model`, `fix/ticker-validation`, `docs/database-design`.

For the first commit only, there is no remote `main` to pull until the repository owner publishes it. Review the scaffold locally before creating that commit or pushing it.

## Working agreements

- Agree on API contracts before building both sides. Keep PRs small enough to explain.
- Add tests for new behavior and bug fixes; avoid tests that require real providers, credentials, or a live database unless explicitly separated as integration tests.
- Commit `frontend/package-lock.json` with dependency changes. Update Python pins deliberately and run the checks after upgrades.
- Use Ruff for Python formatting (`python -m ruff format .` in the configured environment). Follow existing JSX/CSS style.
- Keep secrets, generated files, downloaded datasets, and trained models out of Git. Review staged content before committing.
- Keep future ML training separate from API inference. Document dataset provenance and time-aware evaluation when ML work begins.
- AI-assisted changes need the same human understanding and review as any other change. The author should be able to explain the code and its verification.
- Keep changes within the agreed scope; define a focused task before adding future features.
