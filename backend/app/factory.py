from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.accounts import router as accounts_router
from app.api.health import router as health_router
from app.api.preferences import router as preferences_router
from app.api.sessions import router as sessions_router
from app.api.stocks import router as stocks_router
from app.auth import TokenVerifier
from app.config import Settings
from app.db import database_engine


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        try:
            yield
        finally:
            if application.state.engine is not None:
                application.state.engine.dispose()

    application = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan)
    application.state.settings = settings
    application.state.token_verifier = (
        TokenVerifier(settings)
        if settings.auth0_domain and settings.auth0_audience
        else None
    )
    application.state.engine = (
        database_engine(settings.database_url.get_secret_value())
        if settings.database_url is not None
        else None
    )
    application.include_router(health_router, prefix="/api")
    application.include_router(stocks_router, prefix="/api")
    application.include_router(accounts_router, prefix="/api")
    application.include_router(preferences_router, prefix="/api")
    application.include_router(sessions_router, prefix="/api")

    @application.middleware("http")
    async def private_response_headers(request, call_next):
        response = await call_next(request)
        if request.url.path == "/api/me" or request.url.path.startswith(
            ("/api/watchlist", "/api/auth/", "/api/me/")
        ):
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return application
