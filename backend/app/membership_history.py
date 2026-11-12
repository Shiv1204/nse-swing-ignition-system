"""Point-in-time index membership loader using half-open [from, to) intervals."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path

REQUIRED = {"symbol", "sector", "valid_from", "valid_to", "source", "as_of_date"}
OPTIONAL = {"source_url", "confidence", "notes"}


def load_membership_history(path: str | Path = "data/universe/nse500_membership_history.csv") -> list[dict]:
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"Membership history file not found: {file_path}")
    with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames or not REQUIRED.issubset(reader.fieldnames):
            raise ValueError("Membership history CSV must contain: " + ", ".join(sorted(REQUIRED)))
        rows = []
        for line, raw in enumerate(reader, start=2):
            row = {key: (raw.get(key) or "").strip() for key in REQUIRED | OPTIONAL}
            row["symbol"] = row["symbol"].upper()
            if not row["symbol"] or not row["valid_from"] or not row["source"]:
                raise ValueError(f"Missing required membership value on line {line}")
            start = date.fromisoformat(row["valid_from"])
            end = date.fromisoformat(row["valid_to"]) if row["valid_to"] else None
            date.fromisoformat(row["as_of_date"])
            if end and end <= start:
                raise ValueError(f"valid_to must be after valid_from for a half-open interval on line {line}")
            row["_start"] = start
            row["_end"] = end
            rows.append(row)
    if not rows:
        raise ValueError("Membership history CSV is empty; add verified dated constituent intervals before using point-in-time coverage.")
    by_symbol: dict[str, list[dict]] = {}
    for row in rows:
        by_symbol.setdefault(row["symbol"], []).append(row)
    for symbol, intervals in by_symbol.items():
        intervals.sort(key=lambda item: item["_start"])
        for previous, current in zip(intervals, intervals[1:]):
            if previous["_end"] is None or previous["_end"] > current["_start"]:
                raise ValueError(f"Overlapping membership intervals for {symbol}")
    return rows


def members_on_date(rows: list[dict], as_of: str | date) -> list[dict]:
    target = date.fromisoformat(as_of) if isinstance(as_of, str) else as_of
    return [
        {key: value for key, value in row.items() if not key.startswith("_")}
        for row in rows
        if row["_start"] <= target and (row["_end"] is None or target < row["_end"])
    ]
