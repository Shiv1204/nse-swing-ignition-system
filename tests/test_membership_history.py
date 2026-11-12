from pathlib import Path

import pytest

from backend.app.membership_history import load_membership_history, members_on_date


def test_membership_history_resolves_point_in_time_intervals(tmp_path: Path):
    path = tmp_path / "membership.csv"
    path.write_text(
        "symbol,sector,valid_from,valid_to,source,as_of_date,source_url\n"
        "AAA,IT,2020-01-01,2021-06-30,NSE circular,2020-01-01,https://example.com/a\n"
        "AAA,IT,2021-07-01,,NSE circular,2021-07-01,https://example.com/b\n"
        "BBB,BANK,2021-01-01,,NSE circular,2021-01-01,https://example.com/c\n",
        encoding="utf-8",
    )
    rows = load_membership_history(path)
    assert {row["symbol"] for row in members_on_date(rows, "2021-03-01")} == {"AAA", "BBB"}
    assert {row["symbol"] for row in members_on_date(rows, "2021-06-30")} == {"BBB"}
    assert {row["symbol"] for row in members_on_date(rows, "2021-07-01")} == {"AAA", "BBB"}
    assert {row["symbol"] for row in members_on_date(rows, "2022-01-01")} == {"AAA", "BBB"}


def test_membership_history_rejects_overlapping_intervals(tmp_path: Path):
    path = tmp_path / "membership.csv"
    path.write_text(
        "symbol,sector,valid_from,valid_to,source,as_of_date,source_url\n"
        "AAA,IT,2020-01-01,2021-12-31,NSE circular,2020-01-01,https://example.com/a\n"
        "AAA,IT,2021-01-01,,NSE circular,2021-01-01,https://example.com/b\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Overlapping"):
        load_membership_history(path)
