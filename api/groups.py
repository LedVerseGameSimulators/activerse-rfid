"""Persistent groups under companies + start-visit → session_roster."""
from typing import Optional

from fastapi import HTTPException

from . import players, sessions
from .database import Database


def list_groups(db: Database, company_id: Optional[int] = None, walk_in_only: bool = False):
    return db.list_groups(company_id, walk_in_only=walk_in_only)


def create_group(db: Database, company_id: Optional[int], name: str,
                  leader_player_id: Optional[int] = None):
    if not name or not name.strip():
        raise HTTPException(400, "Group name is required")
    if company_id is not None:
        if not db.get_company(company_id):
            raise HTTPException(404, "Company not found")
        if db.get_group_by_company_name(company_id, name):
            raise HTTPException(400, "Group name already exists in this company")
    if leader_player_id is not None and not db.search_custom_tb_by_id(leader_player_id):
        raise HTTPException(404, "Leader player not found")
    return _group_detail(db, db.create_group(company_id, name.strip(), leader_player_id)["id"])


def get_group(db: Database, group_id: int):
    return _group_detail(db, group_id)


def update_group(db: Database, group_id: int, name: Optional[str] = None):
    row = db.get_group(group_id)
    if not row:
        raise HTTPException(404, "Group not found")
    if name is not None:
        other = db.get_group_by_company_name(row["company_id"], name)
        if other and other["id"] != group_id:
            raise HTTPException(400, "Group name already exists in this company")
    db.update_group(group_id, name=name)
    return _group_detail(db, group_id)


def delete_group(db: Database, group_id: int):
    if not db.get_group(group_id):
        raise HTTPException(404, "Group not found")
    try:
        db.delete_group(group_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {"success": True, "group_id": group_id}


def add_member(db: Database, group_id: int, player_id: Optional[int] = None,
               name: Optional[str] = None, phone: Optional[str] = None,
               email=None, age=None):
    if not db.get_group(group_id):
        raise HTTPException(404, "Group not found")
    pid = player_id
    if pid is None:
        if not phone or not name:
            raise HTTPException(400, "Provide player_id or name+phone")
        pid = _upsert_player_id(db, name, phone, email, age)
    elif not db.search_custom_tb_by_id(pid):
        raise HTTPException(404, "Player not found")
    try:
        db.add_group_member_atomic(group_id, pid)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _group_detail(db, group_id)


def transfer_member(db: Database, new_group_id: int, player_id: int):
    if not db.get_group(new_group_id):
        raise HTTPException(404, "Group not found")
    if not db.search_custom_tb_by_id(player_id):
        raise HTTPException(404, "Player not found")
    try:
        db.transfer_group_member_atomic(new_group_id, player_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _group_detail(db, new_group_id)


def remove_member(db: Database, group_id: int, player_id: int):
    group = db.get_group(group_id)
    if not group:
        raise HTTPException(404, "Group not found")
    if group.get("leader_player_id") == player_id:
        raise HTTPException(400, "Cannot remove the group leader; set a new leader first.")
    n = db.remove_group_member(group_id, player_id)
    if n == 0:
        raise HTTPException(404, "Player is not a member of this group")
    return _group_detail(db, group_id)


def set_leader(db: Database, group_id: int, player_id: int):
    if not db.get_group(group_id):
        raise HTTPException(404, "Group not found")
    if not db.search_custom_tb_by_id(player_id):
        raise HTTPException(404, "Player not found")
    db.set_group_leader(group_id, player_id)
    return _group_detail(db, group_id)


def start_visit(db: Database, group_id: int, duration_min: int, card_id: Optional[str] = None):
    if not db.get_group(group_id):
        raise HTTPException(404, "Group not found")
    try:
        result = db.issue_group_visit_atomic(
            group_id, duration_min, card_id=card_id, notes=f"group:{group_id}"
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    result["minutes_remaining"] = duration_min
    result["roster"] = sessions.get_roster(db, result["session_id"])["roster"]
    return result


def _group_detail(db: Database, group_id: int):
    row = db.get_group(group_id)
    if not row:
        raise HTTPException(404, "Group not found")
    members = db.get_group_members(group_id)
    return {
        "id": row["id"],
        "company_id": row["company_id"],
        "company_name": row.get("company_name"),
        "name": row["name"],
        "leader_player_id": row.get("leader_player_id"),
        "created_at": row.get("created_at"),
        "members": [
            {
                "player_id": m["player_id"],
                "name": m["name"],
                "phone": m.get("phone"),
                "is_leader": bool(m.get("is_leader")),
            }
            for m in members
        ],
    }


def _upsert_player_id(db: Database, name: str, phone: str, email=None, age=None) -> int:
    existing = db.search_custom_by_field("phone_num", phone.strip())
    if existing:
        return existing[0]["custom_id"]
    created = players.register_player(db, name.strip(), phone.strip(), email, age)
    return created["id"]
