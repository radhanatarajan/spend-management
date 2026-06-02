import pytest
from src.models.reference import Department, AccountNumber, ProjectId, ActivityId


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_department(db, code="1100", name="Engineering"):
    dept = Department(department_code=code, department_name=name)
    db.add(dept)
    db.commit()
    db.refresh(dept)
    return dept


def make_account(db, account_group="R&D", cost_element="Licenses", account_sub_group=None):
    acct = AccountNumber(
        account_number="__TEMP__",
        account_group=account_group,
        account_sub_group=account_sub_group,
        cost_element=cost_element,
    )
    db.add(acct)
    db.flush()
    acct.account_number = f"ACC-{acct.id:04d}"
    db.commit()
    db.refresh(acct)
    return acct


def make_project(db, project_name="CAPEX-TEST", departments=None):
    proj = ProjectId(project_number="__TEMP__", project_name=project_name, departments=departments or [])
    db.add(proj)
    db.flush()
    proj.project_number = f"PRJ-{proj.id:04d}"
    db.commit()
    db.refresh(proj)
    return proj


def make_activity(db, activity_id="ACT-001", desc=None, department_code=None, account_id=None, project_id=None):
    act = ActivityId(
        activity_id=activity_id,
        activity_id_desc=desc,
        department_code=department_code,
        account_id=account_id,
        project_id=project_id,
    )
    db.add(act)
    db.commit()
    db.refresh(act)
    return act


# ── Department tests ──────────────────────────────────────────────────────────

class TestDepartments:
    def test_list_empty(self, admin_client):
        r = admin_client.get("/api/departments")
        assert r.status_code == 200
        assert r.json() == []

    def test_create(self, admin_client, db):
        r = admin_client.post("/api/departments", json={"department_code": "1100", "department_name": "Engineering"})
        assert r.status_code == 201
        assert r.json()["department_code"] == "1100"
        assert r.json()["department_name"] == "Engineering"

    def test_create_duplicate_409(self, admin_client, db):
        make_department(db)
        r = admin_client.post("/api/departments", json={"department_code": "1100", "department_name": "Eng"})
        assert r.status_code == 409

    def test_update(self, admin_client, db):
        make_department(db)
        r = admin_client.put("/api/departments/1100", json={"department_name": "Eng Updated"})
        assert r.status_code == 200
        assert r.json()["department_name"] == "Eng Updated"

    def test_update_404(self, admin_client):
        r = admin_client.put("/api/departments/9999", json={"department_name": "X"})
        assert r.status_code == 404

    def test_delete(self, admin_client, db):
        make_department(db)
        r = admin_client.delete("/api/departments/1100")
        assert r.status_code == 204

    def test_delete_409_when_referenced_by_activity(self, admin_client, db):
        dept = make_department(db)
        make_activity(db, department_code=dept.department_code)
        r = admin_client.delete("/api/departments/1100")
        assert r.status_code == 409

    def test_readonly_cannot_create(self, readonly_client):
        r = readonly_client.post("/api/departments", json={"department_code": "9900", "department_name": "X"})
        assert r.status_code == 403

    def test_list_sorted(self, admin_client, db):
        make_department(db, code="1200", name="Sales")
        make_department(db, code="1100", name="Engineering")
        r = admin_client.get("/api/departments")
        codes = [d["department_code"] for d in r.json()]
        assert codes == sorted(codes)


# ── Account Number tests ──────────────────────────────────────────────────────

class TestAccounts:
    def test_list_empty(self, admin_client):
        r = admin_client.get("/api/accounts")
        assert r.status_code == 200
        assert r.json() == []

    def test_create(self, admin_client):
        r = admin_client.post("/api/accounts", json={
            "account_group": "R&D",
            "account_sub_group": "Cloud Infra",
            "cost_element": "Licenses",
        })
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert data["account_number"] == f"ACC-{data['id']:04d}"
        assert data["account_group"] == "R&D"

    def test_filter_by_cost_element(self, admin_client, db):
        make_account(db, cost_element="Licenses")
        make_account(db, cost_element="Salaries")
        r = admin_client.get("/api/accounts?cost_element=Licenses")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["cost_element"] == "Licenses"

    def test_update(self, admin_client, db):
        acct = make_account(db)
        r = admin_client.put(f"/api/accounts/{acct.id}", json={"cost_element": "Hardware"})
        assert r.status_code == 200
        assert r.json()["cost_element"] == "Hardware"

    def test_update_404(self, admin_client):
        r = admin_client.put("/api/accounts/99999", json={"cost_element": "Hardware"})
        assert r.status_code == 404

    def test_delete(self, admin_client, db):
        acct = make_account(db)
        r = admin_client.delete(f"/api/accounts/{acct.id}")
        assert r.status_code == 204

    def test_delete_409_when_referenced(self, admin_client, db):
        acct = make_account(db)
        make_activity(db, account_id=acct.id)
        r = admin_client.delete(f"/api/accounts/{acct.id}")
        assert r.status_code == 409

    def test_readonly_cannot_create(self, readonly_client):
        r = readonly_client.post("/api/accounts", json={
            "account_group": "G&A", "cost_element": "Salaries",
        })
        assert r.status_code == 403


# ── Project ID tests ──────────────────────────────────────────────────────────

class TestProjects:
    def test_list_empty(self, admin_client):
        r = admin_client.get("/api/projects")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_no_departments(self, admin_client):
        r = admin_client.post("/api/projects", json={"project_name": "CAPEX-TEST"})
        assert r.status_code == 201
        data = r.json()
        assert "id" in data
        assert data["project_number"] == f"PRJ-{data['id']:04d}"
        assert data["project_name"] == "CAPEX-TEST"
        assert data["departments"] == []

    def test_create_with_departments(self, admin_client, db):
        make_department(db, "1100", "Engineering")
        make_department(db, "1200", "Sales")
        r = admin_client.post("/api/projects", json={
            "project_name": "CAPEX-TEST", "department_codes": ["1100", "1200"],
        })
        assert r.status_code == 201
        dept_codes = {d["department_code"] for d in r.json()["departments"]}
        assert dept_codes == {"1100", "1200"}

    def test_create_unknown_dept_422(self, admin_client):
        r = admin_client.post("/api/projects", json={"project_name": "CAPEX-TEST", "department_codes": ["9999"]})
        assert r.status_code == 422

    def test_create_duplicate_409(self, admin_client, db):
        make_project(db)
        r = admin_client.post("/api/projects", json={"project_name": "CAPEX-TEST"})
        assert r.status_code == 409

    def test_filter_by_department(self, admin_client, db):
        eng = make_department(db, "1100", "Engineering")
        sales = make_department(db, "1200", "Sales")
        make_project(db, "PROJ-A", departments=[eng])
        make_project(db, "PROJ-B", departments=[sales])
        make_project(db, "PROJ-C", departments=[eng, sales])

        r = admin_client.get("/api/projects?department_code=1100")
        assert r.status_code == 200
        names = {p["project_name"] for p in r.json()}
        assert names == {"PROJ-A", "PROJ-C"}

    def test_update_departments(self, admin_client, db):
        eng = make_department(db, "1100", "Engineering")
        make_department(db, "1200", "Sales")
        proj = make_project(db, departments=[eng])
        r = admin_client.put(f"/api/projects/{proj.id}", json={"department_codes": ["1200"]})
        assert r.status_code == 200
        dept_codes = [d["department_code"] for d in r.json()["departments"]]
        assert dept_codes == ["1200"]

    def test_delete(self, admin_client, db):
        proj = make_project(db)
        r = admin_client.delete(f"/api/projects/{proj.id}")
        assert r.status_code == 204

    def test_delete_409_when_referenced(self, admin_client, db):
        proj = make_project(db)
        make_activity(db, project_id=proj.id)
        r = admin_client.delete(f"/api/projects/{proj.id}")
        assert r.status_code == 409

    def test_readonly_cannot_create(self, readonly_client):
        r = readonly_client.post("/api/projects", json={"project_name": "CAPEX-X"})
        assert r.status_code == 403


# ── Activity ID tests ─────────────────────────────────────────────────────────

class TestActivities:
    def test_list_empty(self, admin_client):
        r = admin_client.get("/api/activities")
        assert r.status_code == 200
        assert r.json() == []

    def test_create_minimal(self, admin_client):
        r = admin_client.post("/api/activities", json={"activity_id": "ACT-001"})
        assert r.status_code == 201
        assert r.json()["activity_id"] == "ACT-001"
        assert r.json()["department_code"] is None

    def test_create_with_references(self, admin_client, db):
        dept = make_department(db)
        acct = make_account(db)
        proj = make_project(db)
        r = admin_client.post("/api/activities", json={
            "activity_id": "ACT-001",
            "activity_id_desc": "Test activity",
            "department_code": dept.department_code,
            "account_id": acct.id,
            "project_id": proj.id,
        })
        assert r.status_code == 201
        data = r.json()
        assert data["department_code"] == "1100"
        assert data["department_name"] == "Engineering"
        assert data["account_id"] == acct.id
        assert data["account_number"] == acct.account_number
        assert data["cost_element"] == "Licenses"
        assert data["project_id"] == proj.id
        assert data["project_number"] == proj.project_number
        assert data["project_name"] == proj.project_name

    def test_create_duplicate_409(self, admin_client, db):
        make_activity(db)
        r = admin_client.post("/api/activities", json={"activity_id": "ACT-001"})
        assert r.status_code == 409

    def test_filter_by_department(self, admin_client, db):
        make_department(db, "1100", "Engineering")
        make_department(db, "1200", "Sales")
        make_activity(db, "ACT-001", department_code="1100")
        make_activity(db, "ACT-002", department_code="1200")
        r = admin_client.get("/api/activities?department_code=1100")
        assert r.status_code == 200
        assert len(r.json()) == 1
        assert r.json()[0]["activity_id"] == "ACT-001"

    def test_update(self, admin_client, db):
        make_activity(db)
        r = admin_client.put("/api/activities/ACT-001", json={"activity_id_desc": "Updated desc"})
        assert r.status_code == 200
        assert r.json()["activity_id_desc"] == "Updated desc"

    def test_delete(self, admin_client, db):
        make_activity(db)
        r = admin_client.delete("/api/activities/ACT-001")
        assert r.status_code == 204

    def test_delete_404(self, admin_client):
        r = admin_client.delete("/api/activities/NONEXISTENT")
        assert r.status_code == 404

    def test_readonly_cannot_create(self, readonly_client):
        r = readonly_client.post("/api/activities", json={"activity_id": "ACT-X"})
        assert r.status_code == 403

    def test_readonly_can_list(self, readonly_client):
        r = readonly_client.get("/api/activities")
        assert r.status_code == 200
