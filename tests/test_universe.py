import pytest

from backend.app.universe import load_universe


HEADER = "symbol,company_name,sector,exchange,valid_from,valid_to,source,as_of_date\n"


def test_load_universe_requires_provenance(tmp_path) -> None:
    path = tmp_path / "nse500.csv"
    path.write_text(
        HEADER + "RELIANCE,Reliance Industries,Energy,NSE,2026-01-01,,official-index-csv,2026-11-01\n",
        encoding="utf-8",
    )
    result = load_universe(path)
    assert result["count"] == 1
    assert result["constituents"][0]["symbol"] == "RELIANCE"


def test_load_universe_rejects_duplicate_symbols(tmp_path) -> None:
    path = tmp_path / "nse500.csv"
    row = "RELIANCE,Reliance Industries,Energy,NSE,2026-01-01,,official-index-csv,2026-11-01\n"
    path.write_text(HEADER + row + row, encoding="utf-8")
    with pytest.raises(ValueError, match="Duplicate symbol"):
        load_universe(path)


def test_load_universe_rejects_empty_template(tmp_path) -> None:
    path = tmp_path / "nse500.csv"
    path.write_text(HEADER, encoding="utf-8")
    with pytest.raises(ValueError, match="currently empty"):
        load_universe(path)


def test_load_universe_rejects_missing_source_date(tmp_path) -> None:
    path = tmp_path / "nse500.csv"
    path.write_text(
        HEADER + "RELIANCE,Reliance Industries,Energy,NSE,2026-01-01,,,\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="source and as_of_date"):
        load_universe(path)
