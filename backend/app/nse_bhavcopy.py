"""Import NSE cash-market daily bhavcopy files (legacy CSV and UDiFF ZIP/CSV)."""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import date, datetime, time
from pathlib import Path

from backend.app.market_data import MarketDataStore
from backend.app.schemas import OHLCVBar


def _first(row: dict, names: tuple[str, ...]) -> str:
    for name in names:
        value = row.get(name)
        if value is not None and str(value).strip():
            return str(value).strip()
    raise ValueError(f"Missing required field; expected one of {', '.join(names)}")


def _trade_date(value: str) -> date:
    value = value.strip()
    for fmt in ("%Y-%m-%d", "%d-%b-%Y", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unsupported NSE trade date: {value}")


def _read_csv_payload(path: Path) -> tuple[list[dict], str]:
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            candidates = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(candidates) != 1:
                raise ValueError("Bhavcopy ZIP must contain exactly one CSV file")
            raw = archive.read(candidates[0])
    else:
        raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise ValueError("Bhavcopy file has no header row")
    return list(reader), ",".join(reader.fieldnames)


def import_nse_bhavcopy(
    file_path: str | Path,
    store: MarketDataStore,
    series: str = "EQ",
    source: str = "nse_bhavcopy",
) -> dict:
    """Import one NSE cash bhavcopy; only EQ-series cash-market shares are accepted."""
    path = Path(file_path)
    rows, header = _read_csv_payload(path)
    imported: dict[str, list[OHLCVBar]] = {}
    rejected = {"wrong_segment_or_instrument": 0, "wrong_series": 0, "invalid_rows": 0}
    dates: set[str] = set()
    for row in rows:
        try:
            segment = (row.get("Sgmt") or "CM").strip().upper()
            instrument = (row.get("FinInstrmTp") or "STK").strip().upper()
            if segment not in {"CM", ""} or instrument not in {"STK", ""}:
                rejected["wrong_segment_or_instrument"] += 1
                continue
            row_series = _first(row, ("SctySrs", "SERIES")).upper()
            if row_series != series.upper():
                rejected["wrong_series"] += 1
                continue
            symbol = _first(row, ("TckrSymb", "SYMBOL")).upper()
            trade_day = _trade_date(_first(row, ("TradDt", "BizDt", "TIMESTAMP", "DATE1", "DATE")))
            bar = OHLCVBar(
                timestamp=datetime.combine(trade_day, time.min),
                open=float(_first(row, ("OpnPric", "OPEN_PRICE", "OPEN"))),
                high=float(_first(row, ("HghPric", "HIGH_PRICE", "HIGH"))),
                low=float(_first(row, ("LwPric", "LOW_PRICE", "LOW"))),
                close=float(_first(row, ("ClsPric", "CLOSE_PRICE", "CLOSE"))),
                volume=float(_first(row, ("TtlTradgVol", "TOTTRDQTY", "TTL_TRD_QNTY"))),
            )
            imported.setdefault(symbol, []).append(bar)
            dates.add(trade_day.isoformat())
        except (ValueError, TypeError, KeyError):
            rejected["invalid_rows"] += 1
    if not imported:
        raise ValueError(f"No valid {series.upper()} cash-equity rows found in {path.name}; headers: {header}")
    totals = {"inserted": 0, "updated": 0}
    for symbol, bars in imported.items():
        result = store.upsert_bars(symbol, "1d", bars, source=source)
        totals["inserted"] += result["inserted"]
        totals["updated"] += result["updated"]
    return {
        "file": path.name,
        "symbols": len(imported),
        "symbol_list": sorted(imported),
        "rows_imported": sum(len(bars) for bars in imported.values()),
        "trading_dates": sorted(dates),
        **totals,
        "rejected_rows": rejected,
        "format": "UDiFF" if "TckrSymb" in header else "legacy",
        "source": source,
        "warning": "NSE bhavcopy prices are raw exchange closes, not adjusted for splits, bonuses or other corporate actions. Do not mix these raw bars with adjusted provider histories in one backtest without a corporate-action adjustment layer.",
    }


def import_nse_bhavcopy_directory(
    directory: str | Path,
    store: MarketDataStore,
    pattern: str = "*.zip",
    series: str = "EQ",
) -> dict:
    """Import a folder of daily NSE bhavcopy ZIPs in deterministic filename order."""
    files = sorted(Path(directory).glob(pattern))
    if not files:
        raise FileNotFoundError(f"No files matching {pattern!r} found in {directory}")
    reports = [import_nse_bhavcopy(path, store, series=series) for path in files]
    return {
        "files_processed": len(reports),
        "symbols_seen": len({symbol for report in reports for symbol in report["symbol_list"]}),
        "rows_imported": sum(report["rows_imported"] for report in reports),
        "inserted": sum(report["inserted"] for report in reports),
        "updated": sum(report["updated"] for report in reports),
        "files": reports,
    }
