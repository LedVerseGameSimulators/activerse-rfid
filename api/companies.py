"""Company CRUD — enterprise clients (PwC, EY, etc.)."""
from fastapi import HTTPException

from .database import Database


def list_companies(db: Database):
    return db.list_companies()


def create_company(db: Database, name: str, notes: str = ""):
    if not name or not name.strip():
        raise HTTPException(400, "Company name is required")
    existing = db.get_company_by_name(name)
    if existing:
        raise HTTPException(400, f"Company already exists: {existing['name']}")
    return db.create_company(name.strip(), notes or "")


def get_company(db: Database, company_id: int):
    row = db.get_company(company_id)
    if not row:
        raise HTTPException(404, "Company not found")
    row["groups"] = db.list_groups(company_id)
    return row


def update_company(db: Database, company_id: int, name: str = None, notes: str = None):
    if not db.get_company(company_id):
        raise HTTPException(404, "Company not found")
    if name is not None:
        other = db.get_company_by_name(name)
        if other and other["id"] != company_id:
            raise HTTPException(400, f"Company name already used: {other['name']}")
    return db.update_company(company_id, name=name, notes=notes)


def delete_company(db: Database, company_id: int):
    if not db.get_company(company_id):
        raise HTTPException(404, "Company not found")
    db.delete_company(company_id)
    return {"success": True, "company_id": company_id}
