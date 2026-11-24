"""Publish selected non-secret refresh fields to the GitHub Actions summary."""

import argparse
import json
import os
from pathlib import Path


def summary(report):
    rows = report.get("results", [])
    lines = [
        "# Daily price refresh",
        "",
        f"Writes enabled: **{report.get('write_enabled') is True}**",
        "",
        "| Stock | Status | Inserts | Corrections | Missing | Blockers | "
        "Error type | Run ID |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    def cell(value):
        return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")

    for row in rows:
        values = [
            row.get("symbol", "?"),
            row.get("status", "unknown"),
            len(row.get("inserts", [])),
            len(row.get("corrections", [])),
            len(row.get("missing_sessions", [])),
            len(row.get("blockers", [])),
            row.get("error_type", ""),
            row.get("run_id", ""),
        ]
        lines.append("| " + " | ".join(cell(v) for v in values) + " |")
    lines.extend(
        [
            "",
            "Refresh reads completed sessions; it does not provide live quotes.",
            "Blocked/failed stocks keep their prior data. A partial stock may have",
            "committed valid sessions before its first missing session. "
            "Review its result.",
            "",
        ]
    )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    try:
        content = summary(json.loads(args.report.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        content = (
            "# Daily price refresh\n\nNo readable report was produced. "
            "Check failed job steps and the Actions secret configuration.\n"
        )
    print(content)
    destination = os.getenv("GITHUB_STEP_SUMMARY")
    if destination:
        with Path(destination).open("a", encoding="utf-8") as output:
            output.write(content + "\n")


if __name__ == "__main__":
    main()
