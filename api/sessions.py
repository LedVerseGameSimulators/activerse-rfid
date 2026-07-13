"""
Session issue/adjust/close/validate — clock-based expiry_at model.
"""
from datetime import datetime

from fastapi import HTTPException

from .config import DEFAULT_SESSION_MINUTES, MIN_MINUTES_TO_START
from .database import Database


def _minutes_remaining(expiry_at: str) -> float:
    expiry = datetime.strptime(expiry_at, "%Y-%m-%d %H:%M:%S")
    delta = (expiry - datetime.now()).total_seconds() / 60
    return max(0, round(delta, 1))


def issue_session(db: Database, player_id: int, duration_min: int = DEFAULT_SESSION_MINUTES,
                  notes: str = ""):
    """Deducts the full session duration from credit_balance up front, no
    refund on early close or unused expiry (matches the existing clock-based
    player_sessions model exactly)."""
    rows = db.search_custom_tb_by_id(player_id)
    if not rows:
        raise HTTPException(404, "Player not found")

    balance = db.get_credit_balance(player_id)
    if balance < duration_min:
        raise HTTPException(
            400,
            f"Insufficient credit balance: has {balance:.0f} min, "
            f"needs {duration_min} min. Top up first."
        )

    card_id = rows[0].get("card_id") or ""
    sid, issued_at, expiry_at = db.create_session(player_id, card_id, duration_min, notes)
    db.deduct_credit(player_id, duration_min)
    return {
        "session_id": sid,
        "player_id": player_id,
        "card_id": card_id or None,
        "issued_at": issued_at,
        "expiry_at": expiry_at,
        "duration_min": duration_min,
        "minutes_remaining": _minutes_remaining(expiry_at),
        "credit_balance_after": balance - duration_min,
    }


def get_active_sessions(db: Database):
    sessions = db.get_active_sessions()
    for s in sessions:
        s["minutes_remaining"] = _minutes_remaining(s["expiry_at"])
    return sessions


def get_session_detail(db: Database, session_id: int):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    session["minutes_remaining"] = _minutes_remaining(session["expiry_at"])
    adjustments = db._execute(
        "SELECT * FROM session_adjustments WHERE session_id = ? ORDER BY adjusted_at",
        (session_id,),
        fetch="all",
    )
    session["adjustments"] = [dict(a) for a in adjustments] if adjustments else []
    return session


def adjust_session(db: Database, session_id: int, delta_min: int, reason: str = "",
                   adjusted_by: str = ""):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.get("closed_at"):
        raise HTTPException(400, "Session already closed")
    new_expiry = db.adjust_session(session_id, delta_min, reason, adjusted_by)
    return {
        "session_id": session_id,
        "expiry_at": new_expiry,
        "minutes_remaining": _minutes_remaining(new_expiry),
    }


def close_session(db: Database, session_id: int):
    rows = db.close_session(session_id)
    if rows == 0:
        raise HTTPException(404, "Session not found or already closed")
    return {"success": True, "session_id": session_id}


def validate_card(db: Database, card_id: str):
    """Called by game machines — no auth."""
    if not card_id:
        return {"valid": False, "reason": "no_card"}

    session = db.get_active_session_by_card(card_id)
    if not session:
        # Check if player exists but no active session
        players = db.search_custom_by_field("card_id", card_id)
        if not players:
            return {"valid": False, "reason": "card_not_found"}
        return {"valid": False, "reason": "no_active_session"}

    remaining = _minutes_remaining(session["expiry_at"])
    if remaining <= 0:
        return {"valid": False, "reason": "expired", "minutes_remaining": 0}
    if remaining < MIN_MINUTES_TO_START:
        return {
            "valid": False,
            "reason": "insufficient_time",
            "minutes_remaining": remaining,
        }

    return {
        "valid": True,
        "player_name": session.get("player_name"),
        "session_id": session["id"],
        "minutes_remaining": remaining,
    }
