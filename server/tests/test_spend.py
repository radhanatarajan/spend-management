"""
Tests for GET /api/spend/transactions and GET /api/spend/filter-options.
Uses an in-memory SQLite DB — no MySQL or Docker required.
"""
from decimal import Decimal
from tests.conftest import make_spend, TestingSession


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def seed(db, rows):
    db.add_all(rows)
    db.commit()


# ---------------------------------------------------------------------------
# GET /api/spend/transactions
# ---------------------------------------------------------------------------

class TestListTransactions:
    def test_returns_200_with_empty_table(self, client):
        resp = client.get("/api/spend/transactions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["items"] == []
        assert body["total_pages"] == 1

    def test_returns_all_rows(self, client, db):
        seed(db, [make_spend(), make_spend(vendor_name="Zoom")])
        resp = client.get("/api/spend/transactions")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_response_shape(self, client, db):
        seed(db, [make_spend(amount_usd=Decimal("42.50"))])
        item = client.get("/api/spend/transactions").json()["items"][0]
        assert item["vendor_name"] == "AWS"
        assert float(item["amount_usd"]) == 42.50
        assert "month_label" in item
        assert "oracle_department_name" in item

    # --- pagination ---

    def test_pagination_page_size(self, client, db):
        seed(db, [make_spend(vendor_name=f"V{i}") for i in range(10)])
        resp = client.get("/api/spend/transactions?page=1&page_size=4")
        body = resp.json()
        assert len(body["items"]) == 4
        assert body["total"] == 10
        assert body["total_pages"] == 3

    def test_pagination_last_page(self, client, db):
        seed(db, [make_spend(vendor_name=f"V{i}") for i in range(10)])
        resp = client.get("/api/spend/transactions?page=3&page_size=4")
        assert len(resp.json()["items"]) == 2

    def test_pagination_beyond_last_page_returns_empty(self, client, db):
        seed(db, [make_spend()])
        resp = client.get("/api/spend/transactions?page=99&page_size=50")
        assert resp.json()["items"] == []

    # --- filtering ---

    def test_filter_by_expense_type(self, client, db):
        seed(db, [
            make_spend(expense_type="Capex"),
            make_spend(expense_type="Opex"),
            make_spend(expense_type="Opex"),
        ])
        resp = client.get("/api/spend/transactions?expense_types=Opex")
        body = resp.json()
        assert body["total"] == 2
        assert all(r["expense_type"] == "Opex" for r in body["items"])

    def test_filter_by_multiple_expense_types(self, client, db):
        seed(db, [
            make_spend(expense_type="Capex"),
            make_spend(expense_type="Opex"),
            make_spend(expense_type="Travel"),
        ])
        resp = client.get("/api/spend/transactions?expense_types=Capex&expense_types=Travel")
        assert resp.json()["total"] == 2

    def test_filter_by_vendor(self, client, db):
        seed(db, [make_spend(vendor_name="AWS"), make_spend(vendor_name="Zoom")])
        resp = client.get("/api/spend/transactions?vendors=AWS")
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["vendor_name"] == "AWS"

    def test_filter_by_oracle_department(self, client, db):
        seed(db, [
            make_spend(oracle_department="1100", oracle_department_name="Engineering"),
            make_spend(oracle_department="1200", oracle_department_name="Sales"),
        ])
        resp = client.get("/api/spend/transactions?oracle_departments=1100")
        assert resp.json()["total"] == 1

    def test_filter_combination_returns_intersection(self, client, db):
        seed(db, [
            make_spend(expense_type="Capex", vendor_name="AWS"),
            make_spend(expense_type="Opex", vendor_name="AWS"),
            make_spend(expense_type="Capex", vendor_name="Zoom"),
        ])
        resp = client.get("/api/spend/transactions?expense_types=Capex&vendors=AWS")
        assert resp.json()["total"] == 1

    def test_filter_no_match_returns_empty(self, client, db):
        seed(db, [make_spend(vendor_name="AWS")])
        resp = client.get("/api/spend/transactions?vendors=Nonexistent")
        assert resp.json()["total"] == 0

    # --- sorting ---

    def test_sort_by_amount_asc(self, client, db):
        seed(db, [
            make_spend(amount_usd=Decimal("300")),
            make_spend(amount_usd=Decimal("100")),
            make_spend(amount_usd=Decimal("200")),
        ])
        items = client.get("/api/spend/transactions?sort_by=amount_usd&sort_order=asc").json()["items"]
        amounts = [float(i["amount_usd"]) for i in items]
        assert amounts == sorted(amounts)

    def test_sort_by_amount_desc(self, client, db):
        seed(db, [
            make_spend(amount_usd=Decimal("300")),
            make_spend(amount_usd=Decimal("100")),
            make_spend(amount_usd=Decimal("200")),
        ])
        items = client.get("/api/spend/transactions?sort_by=amount_usd&sort_order=desc").json()["items"]
        amounts = [float(i["amount_usd"]) for i in items]
        assert amounts == sorted(amounts, reverse=True)

    def test_invalid_sort_by_defaults_safely(self, client, db):
        seed(db, [make_spend()])
        resp = client.get("/api/spend/transactions?sort_by=__evil__")
        assert resp.status_code == 200

    def test_invalid_sort_order_returns_422(self, client):
        resp = client.get("/api/spend/transactions?sort_order=sideways")
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/spend/filter-options
# ---------------------------------------------------------------------------

class TestFilterOptions:
    def test_returns_200_with_empty_table(self, client):
        resp = client.get("/api/spend/filter-options")
        assert resp.status_code == 200
        body = resp.json()
        assert body["months"] == []
        assert body["expense_types"] == []
        assert body["vendors"] == []

    def test_returns_distinct_expense_types(self, client, db):
        seed(db, [
            make_spend(expense_type="Capex"),
            make_spend(expense_type="Opex"),
            make_spend(expense_type="Capex"),  # duplicate
        ])
        types = client.get("/api/spend/filter-options").json()["expense_types"]
        assert sorted(types) == ["Capex", "Opex"]

    def test_returns_distinct_vendors(self, client, db):
        seed(db, [make_spend(vendor_name="AWS"), make_spend(vendor_name="Zoom")])
        vendors = client.get("/api/spend/filter-options").json()["vendors"]
        assert sorted(vendors) == ["AWS", "Zoom"]

    def test_months_sorted_desc(self, client, db):
        seed(db, [
            make_spend(month_key=202601, month_label="Jan 2026"),
            make_spend(month_key=202603, month_label="Mar 2026"),
            make_spend(month_key=202602, month_label="Feb 2026"),
        ])
        months = client.get("/api/spend/filter-options").json()["months"]
        keys = [m["month_key"] for m in months]
        assert keys == sorted(keys, reverse=True)

    def test_je_sources_excludes_null(self, client, db):
        seed(db, [
            make_spend(je_source="Coupa"),
            make_spend(je_source=None),
        ])
        sources = client.get("/api/spend/filter-options").json()["je_sources"]
        assert None not in sources
        assert "Coupa" in sources

    # --- cross-filtering ---

    def test_cross_filter_vendors_narrow_by_department(self, client, db):
        seed(db, [
            make_spend(oracle_department="1100", vendor_name="AWS"),
            make_spend(oracle_department="1200", vendor_name="Zoom"),
        ])
        # Filtering by dept 1100 should only show AWS in vendors
        resp = client.get("/api/spend/filter-options?oracle_departments=1100")
        vendors = resp.json()["vendors"]
        assert vendors == ["AWS"]

    def test_cross_filter_dept_slicer_still_shows_all_depts(self, client, db):
        seed(db, [
            make_spend(oracle_department="1100", oracle_department_name="Engineering"),
            make_spend(oracle_department="1200", oracle_department_name="Sales"),
        ])
        # Even when filtering by dept 1100, the dept slicer itself shows all depts
        resp = client.get("/api/spend/filter-options?oracle_departments=1100")
        dept_codes = [d["oracle_department"] for d in resp.json()["oracle_departments"]]
        assert "1100" in dept_codes
        assert "1200" in dept_codes

    def test_cross_filter_multiple_active_slicers(self, client, db):
        seed(db, [
            make_spend(expense_type="Capex", oracle_department="1100", vendor_name="AWS"),
            make_spend(expense_type="Opex",  oracle_department="1100", vendor_name="Zoom"),
            make_spend(expense_type="Capex", oracle_department="1200", vendor_name="Figma"),
        ])
        resp = client.get("/api/spend/filter-options?expense_types=Capex&oracle_departments=1100")
        # Vendors cross-filtered by both expense_type=Capex AND dept=1100 → only AWS
        assert resp.json()["vendors"] == ["AWS"]
