"""The typed research-signal connector answers honestly while no model is approved."""

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from test_explore import explore_client as explore_client

from app.config import Settings
from app.factory import create_app
from app.signals import SignalResponse

# The production response documented in FRONTEND_ML_INTEGRATION_SPEC.md section 4.
UNAVAILABLE_AAPL = {
    "schema_version": "1",
    "ticker": "AAPL",
    "status": "unavailable",
    "unavailable_reason": "model_not_approved",
    "message": "No approved model signal is available.",
    "target_kind": None,
    "horizon_sessions": 1,
    "as_of_session": None,
    "target_session": None,
    "published_at": None,
    "direction": None,
    "raw_score": None,
    "probability": None,
    "signal_strength": None,
    "universe_percentile": None,
    "risk_level": None,
    "model_version": None,
    "data_snapshot": None,
    "provenance": None,
}
# TEST FIXTURE ONLY (spec section 4): shape of a future available signal.
AVAILABLE_TEST_FIXTURE = {
    **UNAVAILABLE_AAPL,
    "status": "available",
    "unavailable_reason": None,
    "message": None,
    "target_kind": "relative_return",
    "as_of_session": "2026-11-16",
    "target_session": "2026-11-17",
    "published_at": "2026-11-17T11:30:00Z",
    "raw_score": 0.0012,
    "universe_percentile": 79,
    "model_version": "test-fixture-only",
    "data_snapshot": "test-fixture-only",
    "provenance": "test_fixture",
}


def test_supported_stocks_get_a_typed_unavailable_signal(explore_client):
    response = explore_client.get("/api/stocks/aapl/signals")
    assert response.status_code == 200
    assert response.json() == UNAVAILABLE_AAPL
    explicit = explore_client.get("/api/stocks/MSFT/signals?horizon_sessions=1")
    assert explicit.json() == {**UNAVAILABLE_AAPL, "ticker": "MSFT"}


def test_unknown_symbols_are_404_and_bad_horizons_422(explore_client):
    for symbol in ["NOHIST", "NOPE"]:
        response = explore_client.get(f"/api/stocks/{symbol}/signals")
        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "UNSUPPORTED_SYMBOL"
    # No automatic fallback to the one defined horizon.
    for horizon in ["0", "5", "20", "x"]:
        response = explore_client.get(
            f"/api/stocks/AAPL/signals?horizon_sessions={horizon}"
        )
        assert response.status_code == 422


def test_fixture_mode_and_storage_failure():
    client = TestClient(create_app(Settings(_env_file=None, database_url=None)))
    assert client.get("/api/stocks/AAPL/signals").json() == UNAVAILABLE_AAPL
    assert client.get("/api/stocks/MSFT/signals").status_code == 404


def test_storage_failure_is_a_sanitized_503(tmp_path):
    unmigrated = f"sqlite:///{tmp_path / 'unmigrated.sqlite'}"
    client = TestClient(create_app(Settings(_env_file=None, database_url=unmigrated)))
    response = client.get("/api/stocks/AAPL/signals")
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "DATA_UNAVAILABLE"


@pytest.mark.parametrize(
    "changes",
    [
        {"probability": 0.0},  # zero is a value, not "unavailable"
        {"raw_score": 0.1},
        {"model_version": "v1"},
        {"unavailable_reason": None},
    ],
)
def test_unavailable_responses_cannot_carry_signal_values(changes):
    with pytest.raises(ValidationError):
        SignalResponse.model_validate({**UNAVAILABLE_AAPL, **changes})


@pytest.mark.parametrize(
    "missing", ["as_of_session", "target_session", "model_version", "provenance"]
)
def test_available_signals_need_dates_and_provenance(missing):
    assert SignalResponse.model_validate(AVAILABLE_TEST_FIXTURE).status == "available"
    with pytest.raises(ValidationError):
        SignalResponse.model_validate({**AVAILABLE_TEST_FIXTURE, missing: None})
