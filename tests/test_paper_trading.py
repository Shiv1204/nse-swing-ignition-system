import pytest

from backend.app.paper_trading import get_paper_portfolio, place_paper_order


def test_paper_ledger_buy_sell_and_realized_pnl(tmp_path):
    db = tmp_path / "paper.db"
    buy = place_paper_order(db, "RELIANCE", "buy", 10, 100, 10000)
    assert buy["cash_balance"] == 9000
    sell = place_paper_order(db, "RELIANCE", "sell", 4, 110, 10000)
    assert sell["realized_pnl"] == 40
    portfolio = get_paper_portfolio(db, 10000)
    assert portfolio["cash"] == 9440
    assert portfolio["realized_pnl"] == 40
    assert portfolio["open_positions"][0]["quantity"] == 6


def test_paper_ledger_rejects_oversell_and_insufficient_cash(tmp_path):
    db = tmp_path / "paper.db"
    with pytest.raises(ValueError, match="Insufficient paper cash"):
        place_paper_order(db, "AAA", "buy", 2, 100, 100)
    with pytest.raises(ValueError, match="only 0 shares"):
        place_paper_order(db, "AAA", "sell", 1, 100, 1000)
