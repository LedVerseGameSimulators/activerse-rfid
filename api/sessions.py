"""
Session issue/adjust/close/validate — clock-based expiry_at model.
Team roster: members on an open session share score credit (total/N).
"""
from datetime import datetime

from fastapi import HTTPException

from .config import DEFAULT_SESSION_MINUTES, MIN_MINUTES_TO_START
from .database import Database


def _minutes_remaining(expiry_at: str) -> float:
    expiry = datetime.strptime(expiry_at, "%Y-%m-%d %H:%M:%S")
    delta = (expiry - datetime.now()).total_seconds() / 60
    return max(0, round(delta, 1))


def _roster_payload(db: Database, session_id: int):
    return [
        {
            "player_id": m["player_id"],
            "name": m["name"],
            "phone": m.get("phone"),
            "is_payer": bool(m.get("is_payer")),
        }
        for m in db.get_session_roster(session_id)
    ]


def issue_session(db: Database, player_id: int, duration_min: int = DEFAULT_SESSION_MINUTES,
                  notes: str = ""):
    """Deducts the full session duration from credit_balance up front, no
    refund on early close or unused expiry (matches the existing clock-based
    player_sessions model exactly). Seeds payer onto session_roster."""
    rows = db.search_custom_tb_by_id(player_id)
    if not rows:
        raise HTTPException(404, "Player not found")

    card_id = rows[0].get("card_id") or ""
    if not card_id:
        raise HTTPException(400, "Bind an RFID card before issuing a session.")

    try:
        sid, issued_at, expiry_at, balance_after = db.issue_session_atomic(
            player_id, card_id, duration_min, notes
        )
    except ValueError as e:
        msg = str(e)
        raise HTTPException(404 if msg == "Player not found" else 400, msg)

    return {
        "session_id": sid,
        "player_id": player_id,
        "card_id": card_id or None,
        "issued_at": issued_at,
        "expiry_at": expiry_at,
        "duration_min": duration_min,
        "minutes_remaining": _minutes_remaining(expiry_at),
        "credit_balance_after": balance_after,
        "roster": _roster_payload(db, sid),
    }


def get_active_sessions(db: Database):
    sessions = db.get_active_sessions()
    for s in sessions:
        s["minutes_remaining"] = _minutes_remaining(s["expiry_at"])
        s["roster"] = _roster_payload(db, s["id"])
        s["roster_count"] = len(s["roster"])
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
    session["roster"] = _roster_payload(db, session_id)
    return session


def get_roster(db: Database, session_id: int):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    return {"session_id": session_id, "roster": _roster_payload(db, session_id)}


def add_roster_member(db: Database, session_id: int, player_id: int):
    try:
        db.add_roster_member_atomic(session_id, player_id)
    except ValueError as e:
        msg = str(e)
        code = 404 if msg in ("Session not found", "Player not found") else 400
        raise HTTPException(code, msg)
    return {"success": True, "session_id": session_id, "roster": _roster_payload(db, session_id)}


def remove_roster_member(db: Database, session_id: int, player_id: int):
    session = db.get_session(session_id)
    if not session:
        raise HTTPException(404, "Session not found")
    if session.get("player_id") == player_id:
        raise HTTPException(400, "Cannot remove the session holder (payer/team leader) from the roster.")
    removed = db.remove_roster_member(session_id, player_id)
    if removed == 0:
        raise HTTPException(404, "Player is not on this session roster")
    return {"success": True, "session_id": session_id, "roster": _roster_payload(db, session_id)}


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

    roster = _roster_payload(db, session["id"])
    if not roster:
        # Legacy sessions issued before roster seeding
        roster = [{
            "player_id": session["player_id"],
            "name": session.get("player_name"),
            "is_payer": True,
        }]
        db.add_roster_member(session["id"], session["player_id"])

    return {
        "valid": True,
        "player_name": session.get("player_name"),
        "session_id": session["id"],
        "minutes_remaining": remaining,
        "members": [{"player_id": m["player_id"], "name": m["name"]} for m in roster],
    }
