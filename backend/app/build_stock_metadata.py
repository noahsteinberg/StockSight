"""Rebuild fixtures/stock_metadata.csv from a saved copy of the pinned source page.

Offline and reviewable: it reads a MediaWiki API JSON response saved beforehand
(revisions with content) and the supported symbols (one per line), and writes
only rows for supported symbols whose sector is one of the 11 GICS sectors.

    python -m app.build_stock_metadata page.json symbols.txt \
        app/fixtures/stock_metadata.csv

Review the diff, then update SOURCE in app/stock_metadata.py to the new revision.
"""

import csv
import json
import re
import sys
from pathlib import Path

from app.stock_metadata import SECTORS

LINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]]*)\]\]")
TICKER = re.compile(r"\{\{\s*\w+?\s*(?:Symbol|link)\s*\|\s*([A-Z.]+)")


def clean(cell: str) -> str:
    cell = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", cell, flags=re.S)
    cell = LINK.sub(r"\1", cell)
    cell = re.sub(r"'''?|<[^>]+>", "", cell)
    return cell.replace("&amp;", "&").strip()


def constituents(wikitext: str) -> dict[str, dict[str, str]]:
    table = wikitext[wikitext.index('id="constituents"') :]
    table = table[: table.index("\n|}")]
    rows = {}
    for block in table.split("\n|-")[1:]:
        cells = [cell for cell in re.split(r"\|\|", block.strip()) if cell.strip()]
        ticker = TICKER.search(cells[0]) if cells else None
        if len(cells) < 4 or not ticker:
            continue
        symbol = ticker.group(1).replace(".", "-")
        rows[symbol] = {
            "symbol": symbol,
            "company_name": clean(cells[1]),
            "sector": clean(cells[2]),
            "sub_industry": clean(cells[3]),
        }
    return rows


def main(page_json: str, symbols_file: str, output: str) -> None:
    page = json.loads(Path(page_json).read_text(encoding="utf-8"))
    revision = page["query"]["pages"][0]["revisions"][0]
    rows = constituents(revision["slots"]["main"]["content"])
    symbols = Path(symbols_file).read_text(encoding="utf-8").split()
    kept = [rows[s] for s in symbols if s in rows and rows[s]["sector"] in SECTORS]
    with open(output, "w", encoding="utf-8", newline="\n") as file:
        writer = csv.DictWriter(
            file,
            ["symbol", "company_name", "sector", "sub_industry"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(kept)
    print(
        f"revision {revision['revid']} ({revision['timestamp']}): "
        f"{len(kept)} of {len(symbols)} supported symbols written; "
        f"missing or invalid: {sorted(set(symbols) - {row['symbol'] for row in kept})}"
    )


if __name__ == "__main__":
    main(*sys.argv[1:4])
