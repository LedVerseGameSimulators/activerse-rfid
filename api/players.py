"""
Player CRUD — ported from ui_customer_regist.py and ui_bindcard.py.
Uses custom_info as master player table.
"""
from datetime import datetime
from fastapi import HTTPException

from .database import Database


def _player_row_to_api(row: dict) -> dict:
    return {
        "id": row["custom_id"],
        "phone": row["phone_num"],
        "name": row["name"],
        "email": row.get("email"),
        "age": row.get("age"),
        "public": row["public"] in ("1", 1, True),
        "card_id": row.get("card_id") or None,
        "notes": row.get("notes"),
        "time_left": row.get("time_left"),
        "credit_balance": float(row.get("credit_balance") or 0),
    }


def _apply_org_badges(db: Database, players_api: list) -> list:
    org_map = db.get_company_group_map([p["id"] for p in players_api])
    for p in players_api:
        org = org_map.get(p["id"])
        p["company_id"] = org["company_id"] if org else None
        p["company_name"] = org["company_name"] if org else None
        p["group_id"] = org["group_id"] if org else None
        p["group_name"] = org["group_name"] if org else None
    return players_api


def list_players(db: Database, q: str = ""):
    rows = db.search_custom_multi(q) if q else db.list_all_custom_info()
    return _apply_org_badges(db, [_player_row_to_api(r) for r in rows])


def get_player(db: Database, player_id: int):
    rows = db.search_custom_tb_by_id(player_id)
    if not rows:
        raise HTTPException(404, "Player not found")
    player = _apply_org_badges(db, [_player_row_to_api(rows[0])])[0]
    sessions = db.get_sessions_for_player(player_id)
    scores = db._execute(
        "SELECT * FROM central_scores WHERE player_id = ? ORDER BY played_at DESC LIMIT 50",
        (player_id,),
        fetch="all",
    )
    player["sessions"] = sessions
    player["scores"] = [dict(s) for s in scores] if scores else []
    player["recharge_history"] = db.search_recharge_tb_by_id(player_id)
    return player


def register_player(db: Database, name: str, phone: str, email=None, age=None,
                    public=True, notes=None):
    """Port of ui_customer_regist.register() — phone uniqueness check."""
    result = db.search_custom_by_field("phone_num", phone)
    if len(result) > 0 or phone == "":
        raise HTTPException(400, "Phone already registered or empty")

    rank_str = "1" if public else "0"
    row = db.insert_to_table_custom_tb(phone, name, rank_str, "0", "", "")
    if row != 1:
        raise HTTPException(500, "Registration failed")

    # Optional fields
    new_rows = db.search_custom_by_field("phone_num", phone)
    custom_id = new_rows[0]["custom_id"]
    if email is not None:
        db.update_custom_value(custom_id, "email", email)
    if age is not None:
        db.update_custom_value(custom_id, "age", age)
    if notes:
        db.update_custom_value(custom_id, "notes", notes)

    # Initial recharge_record (amount=0, time=0) — same as original register()
    str_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.insert_to_table_recharge_record(str(custom_id), "0", "0", str_time)

    return get_player(db, custom_id)


def update_player(db: Database, player_id: int, **fields):
    rows = db.search_custom_tb_by_id(player_id)
    if not rows:
        raise HTTPException(404, "Player not found")
    row = rows[0]
    name = fields.get("name", row["name"])
    public = fields.get("public")
    public_str = ("1" if public else "0") if public is not None else row["public"]
    db.update_custom_tb(player_id, row["phone_num"], name, public_str, row["time_left"])
    if fields.get("email") is not None:
        db.update_custom_value(player_id, "email", fields["email"])
    if fields.get("age") is not None:
        db.update_custom_value(player_id, "age", fields["age"])
    if fields.get("notes") is not None:
        db.update_custom_value(player_id, "notes", fields["notes"])
    return get_player(db, player_id)


def bind_card(db: Database, player_id: int, card_id: str):
    """Port of ui_bindcard.bind_card()."""
    if len(card_id) <= 5:
        raise HTTPException(400, "Card ID invalid (must be > 5 chars)")

    existing = db.search_custom_by_field("card_id", card_id)
    if existing and existing[0]["custom_id"] != player_id:
        raise HTTPException(400, "Card already bound to another player")

    result = db.search_custom_tb_by_id(player_id)
    if len(result) != 1:
        raise HTTPException(404, "Player not found")

    custom_info = result[0]
    card_id_old = custom_info.get("card_id") or ""

    # Guard: don't silently orphan an active session by swapping the card
    # out from under it. Staff must close the session first.
    if card_id_old and card_id_old != card_id:
        active = db.get_active_session_by_player(player_id)
        if active:
            raise HTTPException(
                400,
                f"Player has an active session (#{active['id']}, "
                f"{active['expiry_at']}) on their current card — "
                f"close it before rebinding."
            )

    str_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    phone = custom_info["phone_num"]

    row = db.update_custom_value(player_id, "card_id", card_id)
    if row != 1:
        raise HTTPException(500, "Failed to update card_id")

    if card_id_old == "":
        db.insert_to_table_bind_card_record(phone, "1", card_id, str_time)
    else:
        db.insert_to_table_bind_card_record(phone, "0", card_id_old, str_time)
        db.insert_to_table_bind_card_record(phone, "1", card_id, str_time)

    return {"success": True, "card_id": card_id}


def delete_player(db: Database, player_id: int):
    db.delete_player(player_id)
    return {"success": True}


def unbind_card(db: Database, player_id: int):
    result = db.search_custom_tb_by_id(player_id)
    if len(result) != 1:
        raise HTTPException(404, "Player not found")
    custom_info = result[0]
    card_id_old = custom_info.get("card_id") or ""
    if not card_id_old:
        raise HTTPException(400, "No card bound")

    active = db.get_active_session_by_player(player_id)
    if active:
        raise HTTPException(
            400,
            f"Player has an active session (#{active['id']}, "
            f"{active['expiry_at']}) — close it before unbinding."
        )

    str_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.update_custom_value(player_id, "card_id", "")
    db.insert_to_table_bind_card_record(custom_info["phone_num"], "0", card_id_old, str_time)
    return {"success": True}


def topup_player(db: Database, player_id: int, minutes: float, amount_money: float = 0):
    rows = db.search_custom_tb_by_id(player_id)
    if not rows:
        raise HTTPException(404, "Player not found")
    if minutes <= 0:
        raise HTTPException(400, "Minutes must be positive")
    new_balance = db.add_credit(player_id, minutes, amount_money)
    return {"success": True, "credit_balance": new_balance}
