from io import BytesIO
from types import SimpleNamespace

from openpyxl import Workbook


def _upload(rows, headers):
    wb = Workbook()
    ws = wb.active
    ws.append(headers)
    for row in rows:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return SimpleNamespace(file=buf)


HEADERS = ["group_name", "player_name", "phone", "is_team_leader", "email", "age"]


def test_import_creates_company_members_and_group(db):
    from api import companies, import_excel

    company = companies.create_company(db, "Acme")
    upload = _upload([
        ["Team Alpha", "Ada Lovelace", "9990001111", "Y", "ada@acme.test", 30],
        ["Team Alpha", "Alan Turing", "9990002222", "N", "", ""],
    ], HEADERS)

    report = import_excel.import_excel_for_company(db, company["id"], upload)

    assert report["errors"] == []
    members = db.list_company_members(company["id"])
    assert len(members) == 2
    groups = db.list_groups(company["id"])
    assert len(groups) == 1
    assert groups[0]["name"] == "Team Alpha"


def test_import_blank_group_name_creates_company_member_only(db):
    from api import companies, import_excel

    company = companies.create_company(db, "Acme")
    upload = _upload([
        ["", "Solo Player", "9990003333", "N", "", ""],
    ], HEADERS)

    report = import_excel.import_excel_for_company(db, company["id"], upload)

    assert report["errors"] == []
    members = db.list_company_members(company["id"])
    assert len(members) == 1
    assert db.list_groups(company["id"]) == []


def test_import_ignores_company_name_column_if_present(db):
    from api import companies, import_excel

    company_a = companies.create_company(db, "Acme")
    company_b = companies.create_company(db, "Beta")
    headers = ["company_name"] + HEADERS
    upload = _upload([
        ["Beta", "Team X", "Ghost Player", "9990004444", "N", "", ""],
    ], headers)

    report = import_excel.import_excel_for_company(db, company_a["id"], upload)

    assert report["errors"] == []
    assert len(db.list_company_members(company_a["id"])) == 1
    assert len(db.list_company_members(company_b["id"])) == 0
    assert db.get_company_by_name("Beta")["id"] == company_b["id"]
    assert len(db.list_groups(company_b["id"])) == 0


def test_import_reupload_same_file_is_idempotent(db):
    from api import companies, import_excel

    company = companies.create_company(db, "Acme")
    rows = [
        ["Team Alpha", "Ada Lovelace", "9990001111", "Y", "ada@acme.test", 30],
        ["Team Alpha", "Alan Turing", "9990002222", "N", "", ""],
    ]

    import_excel.import_excel_for_company(db, company["id"], _upload(rows, HEADERS))
    import_excel.import_excel_for_company(db, company["id"], _upload(rows, HEADERS))

    assert len(db.list_company_members(company["id"])) == 2
    assert len(db.list_groups(company["id"])) == 1
    group = db.list_groups(company["id"])[0]
    assert len(db.get_group_members(group["id"])) == 2


def test_import_player_already_in_other_company_is_row_error_not_new_company(db):
    from api import companies, import_excel

    company_a = companies.create_company(db, "Acme")
    company_b = companies.create_company(db, "Beta")
    player_id = None
    db.insert_to_table_custom_tb("9990005555", "Existing Player", "1", "0", "", "")
    player_id = db.search_custom_by_field("phone_num", "9990005555")[0]["custom_id"]
    db.add_company_member_atomic(company_a["id"], player_id)

    upload = _upload([
        ["Team Beta1", "Existing Player", "9990005555", "N", "", ""],
    ], HEADERS)

    report = import_excel.import_excel_for_company(db, company_b["id"], upload)

    assert len(report["errors"]) == 1
    assert db.get_company_membership(player_id)["company_id"] == company_a["id"]
    assert db.list_groups(company_b["id"]) == []
