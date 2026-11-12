"""Import downloaded NSE cash-market daily bhavcopy files into the local SQLite store."""
from __future__ import annotations

import argparse
import json

from backend.app.config import get_settings
from backend.app.market_data import MarketDataStore
from backend.app.nse_bhavcopy import import_nse_bhavcopy, import_nse_bhavcopy_directory

def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", help="NSE bhavcopy CSV/ZIP file or directory")
    parser.add_argument("--directory", action="store_true", help="Import all files matching --pattern")
    parser.add_argument("--pattern", default="*.zip", help="Directory file glob (default: *.zip)")
    parser.add_argument("--series", default="EQ", help="NSE equity series to import (default: EQ)")
    parser.add_argument("--database", default=get_settings().database_path)
    args = parser.parse_args()
    store = MarketDataStore(args.database)
    if args.directory:
        result = import_nse_bhavcopy_directory(args.path, store, pattern=args.pattern, series=args.series)
    else:
        result = import_nse_bhavcopy(args.path, store, series=args.series)
    print(json.dumps(result, indent=2))

if __name__ == "__main__":
    main()
