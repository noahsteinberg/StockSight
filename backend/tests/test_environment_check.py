"""Execution diagnostics must distinguish denied access from stopped services."""

import socket

import pytest

from app import complete_backend as setup
from app import environment_check as check
from app.config import Settings


@pytest.mark.parametrize(
    ("code", "message", "expected"),
    [
        (0, "29.0", "accessible"),
        (1, "permission denied connecting to npipe", "permission_denied"),
        (1, "Access is denied", "permission_denied"),
        (1, "The system cannot find the file specified", "not_running"),
        (1, "unrecognized daemon failure", "unavailable"),
    ],
)
def test_docker_classification(code, message, expected):
    assert check.classify_docker(code, message)["status"] == expected


@pytest.mark.parametrize(
    ("errno", "expected"),
    [
        (10013, "permission_denied"),
        (10061, "not_listening"),
        (13, "permission_denied"),
        (111, "not_listening"),
        (10060, "unavailable"),
    ],
)
def test_loopback_classification(monkeypatch, errno, expected):
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def settimeout(self, value):
            pass

        def connect(self, address):
            raise OSError(errno, "details must not appear in the report")

    monkeypatch.setattr(socket, "socket", lambda *args: Connection())
    assert check.loopback_status(5433) == {"status": expected}


def test_setup_stops_before_validation_if_environment_denies_docker(
    tmp_path,
    monkeypatch,
    capsys,
):
    source = tmp_path / "prices.parquet"
    source.touch()
    monkeypatch.setattr("sys.argv", ["complete_backend", str(source)])
    settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://u:p@127.0.0.1:5433/stocksight",
    )
    monkeypatch.setattr(setup, "Settings", lambda: settings)
    monkeypatch.setattr(
        setup,
        "docker_status",
        lambda: {
            "status": "permission_denied",
            "message": "Access denied to this process.",
        },
    )

    def unexpected_scan(*args):
        pytest.fail("Do not scan millions of rows when Docker access is already denied")

    monkeypatch.setattr(setup, "scan", unexpected_scan)
    assert setup.main() == 1
    output = capsys.readouterr().out
    assert "DOCKER_PERMISSION_DENIED" in output
    assert "BACKEND VERIFIED" not in output
    assert "u:p" not in output
