from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from backend.app.market_data import MarketDataStore
from backend.app.nse_bhavcopy import import_nse_bhavcopy


def test_import_udiff_cash_bhavcopy_zip(tmp_path: Path):
    csv_text = (
        "TradDt,Sgmt,FinInstrmTp,TckrSymb,SctySrs,OpnPric,HghPric,LwPric,ClsPric,TtlTradgVol\n"
        "2025-01-02,CM,STK,RELIANCE,EQ,100,110,99,108,12345\n"
        "2025-01-02,CM,STK,RELIANCE,BE,100,110,99,108,100\n"
        "2025-01-02,FO,FUTSTK,RELIANCE,XX,100,110,99,108,100\n"
        "2025-01-02,CM,STK,TCS,EQ,200,210,199,208,5432\n"
    )
    archive = tmp_path / "BhavCopy_NSE_CM_20250102.zip"
    with ZipFile(archive, "w", ZIP_DEFLATED) as zipped:
        zipped.writestr("bhavcopy.csv", csv_text)
    store = MarketDataStore(tmp_path / "market.db")
    result = import_nse_bhavcopy(archive, store)
    assert result["symbols"] == 2
    assert result["rows_imported"] == 2
    assert result["rejected_rows"]["wrong_series"] == 1
    assert result["rejected_rows"]["wrong_segment_or_instrument"] == 1
    assert store.get_bars("RELIANCE", "1d")[0]["close"] == 108


def test_import_legacy_nse_bhavcopy_csv(tmp_path: Path):
    csv_path = tmp_path / "legacy.csv"
    csv_path.write_text(
        "SYMBOL,SERIES,DATE1,OPEN,HIGH,LOW,CLOSE,TOTTRDQTY\n"
        "INFY,EQ,02-JAN-2020,700,710,695,705,10000\n",
        encoding="utf-8",
    )
    store = MarketDataStore(tmp_path / "market.db")
    result = import_nse_bhavcopy(csv_path, store)
    assert result["format"] == "legacy"
    assert result["rows_imported"] == 1
    assert store.get_bars("INFY", "1d")[0]["close"] == 705

def test_import_nse_full_bhavdata_format(tmp_path: Path):
    csv_path = tmp_path / "sec_bhavdata_full_02012025.csv"
    csv_path.write_text(
        "SYMBOL,SERIES,DATE1,OPEN_PRICE,HIGH_PRICE,LOW_PRICE,CLOSE_PRICE,TTL_TRD_QNTY,TURNOVER_LACS\\n"
        "HDFCBANK,EQ,02-Jan-2025,1600,1620,1590,1610,250000,4000\\n",
        encoding="utf-8",
    )
    store = MarketDataStore(tmp_path / "market.db")
    result = import_nse_bhavcopy(csv_path, store)
    assert result["rows_imported"] == 1
    assert result["format"] == "legacy"
    assert store.get_bars("HDFCBANK", "1d")[0]["close"] == 1610
