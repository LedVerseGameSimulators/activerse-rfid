"""P1: manual top-up with cost 0 remains allowed."""
from api import players

from tests.test_step0_poller_and_leaderboard import _make_player


def test_topup_with_zero_money(db):
    pid = _make_player(db, "555-p601", "Promo")
    out = players.topup_player(db, pid, 30.0, amount_money=0)
    assert out["credit_balance"] == 30.0
    rec = db.search_recharge_tb_by_id(pid)
    assert len(rec) >= 1
    assert rec[0]["money"] == "0.0" or rec[0]["money"] == "0"
