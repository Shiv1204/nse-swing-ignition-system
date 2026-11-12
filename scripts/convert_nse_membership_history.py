"""Convert a third-party NSE index-history export into the NSIS membership schema."""
from __future__ import annotations
import argparse
import csv
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

def convert(source_path: Path, output_path: Path, as_of_date: str) -> dict:
    captured = date.fromisoformat(as_of_date)
    required = {"index_name", "symbol", "valid_from", "valid_to", "source"}
    output_rows = []
    confidence_counts = Counter()
    with source_path.open("r", encoding="utf-8-sig", newline="") as source:
        reader = csv.DictReader(source)
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Source CSV must contain: " + ", ".join(sorted(required)))
        for row in reader:
            if (row.get("index_name") or "").strip().casefold() not in {"nifty 500", "nifty500"}:
                continue
            start = date.fromisoformat(row["valid_from"].strip())
            raw_end = (row.get("valid_to") or "").strip()
            # Source uses half-open [valid_from, valid_to); NSIS stores inclusive valid_to.
            end = (date.fromisoformat(raw_end) - timedelta(days=1)).isoformat() if raw_end else ""
            if end and date.fromisoformat(end) < start:
                raise ValueError(f"Invalid membership interval for {row[chr(115)+chr(121)+chr(109)+chr(98)+chr(111)+chr(108)]}")
            provenance = (row.get("source") or "unspecified").strip()
            confidence = "exact_event_date" if provenance in {"press_release", "circular", "merger"} else "snapshot_floor_or_inferred"
            confidence_counts[confidence] += 1
            output_rows.append({
                "symbol": (row.get("symbol") or "").strip().upper(),
                "sector": "",
                "valid_from": start.isoformat(),
                "valid_to": end,
                "source": provenance,
                "as_of_date": captured.isoformat(),
                "source_url": (row.get("source_url") or "").strip(),
                "confidence": confidence,
                "notes": (row.get("notes") or "").strip(),
            })
    if not output_rows:
        raise ValueError("No Nifty 500 rows found in source CSV")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["symbol", "sector", "valid_from", "valid_to", "source", "as_of_date", "source_url", "confidence", "notes"]
    with output_path.open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=fields)
        writer.writeheader()
        writer.writerows(output_rows)
    return {"rows_written": len(output_rows), "unique_symbols": len({r["symbol"] for r in output_rows}), "confidence_counts": dict(confidence_counts), "output": str(output_path)}

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_csv", type=Path)
    parser.add_argument("--output", type=Path, default=Path("data/universe/nse500_membership_history.csv"))
    parser.add_argument("--as-of-date", required=True, help="Date this source export was captured/validated (YYYY-MM-DD)")
    args = parser.parse_args()
    print(convert(args.source_csv, args.output, args.as_of_date))

if __name__ == "__main__":
    main()
