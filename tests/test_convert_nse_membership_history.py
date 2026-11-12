from pathlib import Path

from scripts.convert_nse_membership_history import convert
from backend.app.membership_history import load_membership_history, members_on_date

def test_converter_filters_nifty500_and_converts_half_open_end_date(tmp_path: Path):
    source = tmp_path / "source.csv"
    source.write_text(
        "index_id,index_name,symbol,valid_from,valid_to,source,source_url,notes\n"
        "221,Nifty 500,AAA,2020-01-01,2020-02-01,press_release,https://example.com/a,added\n"
        "217,Nifty 50,BBB,2020-01-01,,snapshot_floor,,other index\n"
        "221,Nifty 500,CCC,2020-02-01,,snapshot_floor,,current\n",
        encoding="utf-8",
    )
    output = tmp_path / "nse500_membership_history.csv"
    result = convert(source, output, "2026-11-02")
    assert result["rows_written"] == 2
    rows = load_membership_history(output)
    assert len(rows) == 2
    assert {row["symbol"] for row in members_on_date(rows, "2020-01-31")} == {"AAA"}
    assert {row["symbol"] for row in members_on_date(rows, "2020-02-01")} == {"CCC"}
    assert rows[0]["confidence"] == "exact_event_date"
