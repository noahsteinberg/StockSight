"""Hosted entrypoint: production must never silently select the local fixture."""

from app.config import Settings
from app.factory import create_app


def create_hosted_app():
    settings = Settings(_env_file=None)
    if settings.database_url is None:
        raise RuntimeError("Set STOCKSIGHT_DATABASE_URL in the Vercel environment")
    if not settings.app_origin.startswith("https://"):
        raise RuntimeError("Set STOCKSIGHT_APP_ORIGIN to the production HTTPS origin")
    if not settings.auth0_domain or not settings.auth0_audience:
        raise RuntimeError("Configure the hosted Auth0 domain and audience")
    return create_app(settings)


app = create_hosted_app()
