from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.stocks import router as stocks_router
from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings if settings is not None else Settings()
    application = FastAPI(title=settings.app_name, version="0.1.0")
    application.state.settings = settings
    application.include_router(health_router, prefix="/api")
    application.include_router(stocks_router, prefix="/api")
    return application


app = create_app()
