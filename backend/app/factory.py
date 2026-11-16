from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.stocks import router as stocks_router
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
    application.state.engine = (
        database_engine(settings.database_url.get_secret_value())
        if settings.database_url is not None
        else None
    )
    application.include_router(health_router, prefix="/api")
    application.include_router(stocks_router, prefix="/api")
    return application
