"""Load and validate the dated NSE/Nifty 500 constituent CSV."""
from __future__ import annotations

import csv
from pathlib import Path

DEFAULT_UNIVERSE_PATH = Path("data/universe/nse500.csv")
REQUIRED_COLUMNS = {
    "symbol", "company_name", "sector", "exchange",
    "valid_from", "valid_to", "source", "as_of_date",
}


def load_universe(path: str | Path = DEFAULT_UNIVERSE_PATH) -> dict:
    """Load a populated universe file; fail closed if its provenance is missing."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Universe file not found: {file_path}")

    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED_COLUMNS.issubset(set(reader.fieldnames)):
            raise ValueError(
                "Universe CSV must contain: " + ", ".join(sorted(REQUIRED_COLUMNS))
            )
        rows = []
        seen = set()
        for line_number, raw in enumerate(reader, start=2):
            row = {key: (raw.get(key) or "").strip() for key in REQUIRED_COLUMNS}
            if not row["symbol"]:
                raise ValueError(f"Missing symbol on universe CSV line {line_number}")
            symbol = row["symbol"].upper()
            if symbol in seen:
                raise ValueError(f"Duplicate symbol {symbol} in universe CSV")
            seen.add(symbol)
            if not row["source"] or not row["as_of_date"]:
                raise ValueError(
                    f"Universe CSV line {line_number} must include source and as_of_date"
                )
            row["symbol"] = symbol
            rows.append(row)

    if not rows:
        raise ValueError(
            "NSE 500 universe file is currently empty. Populate it from a verified, dated constituent CSV."
        )
    if len(rows) > 500:
        raise ValueError(f"Universe contains {len(rows)} rows; expected at most 500.")
    return {
        "count": len(rows),
        "as_of_date": rows[0]["as_of_date"],
        "source": rows[0]["source"],
        "constituents": rows,
    }
