"""Read-only local diagnosis: python -m app.doctor. No secrets in output."""

from pydantic import ValidationError
from sqlalchemy.exc import ArgumentError

from app.config import Settings
from app.db import database_engine
from app.storage import storage_problem


def main() -> int:
    try:
        settings = Settings()
        engine = (
            database_engine(settings.database_url.get_secret_value())
            if settings.database_url is not None
            else None
        )
    except (ValidationError, ArgumentError, ImportError):
        print("CONFIGURATION_ERROR: Check backend/.env and installed dependencies.")
        return 1
    try:
        problem = storage_problem(engine)
        if problem:
            print(f"{problem['code']}: {problem['message']}")
            print("Setup steps: docs/LOCAL_START.md (from the repository root).")
            return 1
        mode = "database" if engine is not None else "fixture"
        print(f"Storage ready: {mode}. Website: http://127.0.0.1:5173")
        return 0
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
