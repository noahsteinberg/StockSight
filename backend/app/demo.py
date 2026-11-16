"""Explicit offline demo factory; deliberately ignores database environment values."""

from app.config import Settings
from app.factory import create_app


def create_demo_app():
    return create_app(Settings(_env_file=None, database_url=None))
