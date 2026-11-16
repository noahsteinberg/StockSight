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
    """Check schema and usable data without seeding or falling back."""
    from fastapi import HTTPException

    from app.storage import storage_problem

    engine = request.app.state.engine
    problem = storage_problem(engine)
    if problem:
        raise HTTPException(503, detail=problem)
    return {"status": "ok", "storage": "fixture" if engine is None else "database"}
