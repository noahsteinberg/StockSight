from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health_returns_service_contract():
    settings = Settings(_env_file=None, app_name="stocksight-api")
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"status": "ok", "service": "stocksight-api"}
