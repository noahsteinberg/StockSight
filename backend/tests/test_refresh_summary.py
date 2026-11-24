"""Job summaries preserve failures without printing arbitrary report fields."""

import importlib.util
from pathlib import Path


def test_summary_retains_failures_and_excludes_private_fields():
    path = Path(__file__).resolve().parents[2] / "scripts/summarize_refresh.py"
    spec = importlib.util.spec_from_file_location("refresh_summary", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    content = module.summary(
        {
            "write_enabled": True,
            "database_url": "private-value-must-not-appear",
            "results": [
                {"symbol": "AAPL", "status": "success", "inserts": ["2026-11-23"]},
                {
                    "symbol": "MSFT",
                    "status": "error",
                    "error_type": "TimeoutError",
                    "message": "another-private-value",
                },
                {"symbol": "NVDA", "status": "partial", "missing_sessions": ["date"]},
            ],
        }
    )
    assert "| AAPL | success | 1 |" in content
    assert "TimeoutError" in content and "| MSFT | error |" in content
    assert "| NVDA | partial | 0 | 0 | 1 |" in content
    assert "private-value" not in content
    assert "partial stock may have" in content
