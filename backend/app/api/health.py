from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str


@router.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    """Report process health; this does not check external dependencies."""
    return HealthResponse(service=request.app.state.settings.app_name)


@router.get("/ready")
def readiness(request: Request):
    """Check configured storage and schema without changing liveness behavior."""
    from fastapi import HTTPException
    from sqlalchemy import select, text
    from sqlalchemy.exc import SQLAlchemyError

    from app.db import DailyBar

    engine = request.app.state.engine
    if engine is None:
        return {"status": "ok", "storage": "fixture"}
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            connection.execute(select(DailyBar.session_date).limit(1))
    except SQLAlchemyError:
        raise HTTPException(503, detail={"code": "STORAGE_UNAVAILABLE"}) from None
    return {"status": "ok", "storage": "database"}
