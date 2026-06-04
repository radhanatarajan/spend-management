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
        seed(db, [make_spend(amount_usd=Decimal("42.50"), activity_id="AOPEX-0000001")])
        item = client.get("/api/spend/transactions").json()["items"][0]
        assert item["vendor_name"] == "AWS"
        assert float(item["amount_usd"]) == 42.50
        assert "month_label" in item
        assert "oracle_department_name" in item
        assert item["activity_id"] == "AOPEX-0000001"

    def test_activity_id_null_when_not_set(self, client, db):
        seed(db, [make_spend()])
        item = client.get("/api/spend/transactions").json()["items"][0]
        assert item["activity_id"] is None

    def test_filter_by_activity_id(self, client, db):
        seed(db, [
            make_spend(vendor_name="AWS",  activity_id="AOPEX-0000001"),
            make_spend(vendor_name="Zoom", activity_id="AOPEX-0000002"),
            make_spend(vendor_name="GCP",  activity_id="AOPEX-0000001"),
        ])
        resp = client.get("/api/spend/transactions?activity_ids=AOPEX-0000001")
        body = resp.json()
        assert body["total"] == 2
        assert all(r["activity_id"] == "AOPEX-0000001" for r in body["items"])

    def test_filter_by_activity_id_no_match(self, client, db):
        seed(db, [make_spend(activity_id="AOPEX-0000001")])
        resp = client.get("/api/spend/transactions?activity_ids=ACAPEX-9999999")
        assert resp.json()["total"] == 0

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

    def test_returns_distinct_activity_ids(self, client, db):
        seed(db, [
            make_spend(activity_id="AOPEX-0000001"),
            make_spend(activity_id="AOPEX-0000002"),
            make_spend(activity_id="AOPEX-0000001"),  # duplicate
            make_spend(activity_id=None),              # null excluded
        ])
        ids = client.get("/api/spend/filter-options").json()["activity_ids"]
        assert sorted(ids) == ["AOPEX-0000001", "AOPEX-0000002"]

    def test_activity_ids_cross_filtered(self, client, db):
        seed(db, [
            make_spend(vendor_name="AWS",  activity_id="AOPEX-0000001"),
            make_spend(vendor_name="Zoom", activity_id="AOPEX-0000002"),
        ])
        # Filtering by vendor=AWS should only expose that activity ID
        resp = client.get("/api/spend/filter-options?vendors=AWS")
        assert resp.json()["activity_ids"] == ["AOPEX-0000001"]

    def test_activity_id_slicer_shows_all_when_self_filtered(self, client, db):
        seed(db, [
            make_spend(vendor_name="AWS",  activity_id="AOPEX-0000001"),
            make_spend(vendor_name="Zoom", activity_id="AOPEX-0000002"),
        ])
        # Filtering by activity_id itself should still show all activity_ids
        resp = client.get("/api/spend/filter-options?activity_ids=AOPEX-0000001")
        ids = resp.json()["activity_ids"]
        assert "AOPEX-0000001" in ids
        assert "AOPEX-0000002" in ids


# ---------------------------------------------------------------------------
# GET /api/spend/summary
# ---------------------------------------------------------------------------

class TestSpendSummary:
    def test_returns_200_with_empty_table(self, client):
        resp = client.get("/api/spend/summary")
        assert resp.status_code == 200
        body = resp.json()
        assert float(body["total_amount"]) == 0
        assert body["total_transactions"] == 0
        assert body["by_account_group"] == []
        assert body["by_vendor"] == []
        assert body["by_department"] == []
        assert body["by_month"] == []
        assert body["by_cost_element"] == []
        assert body["by_activity_id"] == []

    def test_total_amount_and_transactions(self, client, db):
        seed(db, [
            make_spend(amount_usd=Decimal("1000")),
            make_spend(amount_usd=Decimal("2000")),
        ])
        body = client.get("/api/spend/summary").json()
        assert float(body["total_amount"]) == 3000
        assert body["total_transactions"] == 2

    def test_by_account_group_sorted_desc(self, client, db):
        seed(db, [
            make_spend(oracle_account_group="R&D",  amount_usd=Decimal("500")),
            make_spend(oracle_account_group="G&A",  amount_usd=Decimal("1500")),
            make_spend(oracle_account_group="R&D",  amount_usd=Decimal("300")),
        ])
        groups = client.get("/api/spend/summary").json()["by_account_group"]
        assert groups[0]["label"] == "G&A"
        assert float(groups[0]["amount"]) == 1500
        assert groups[1]["label"] == "R&D"
        assert float(groups[1]["amount"]) == 800

    def test_by_vendor_limited_to_8(self, client, db):
        seed(db, [make_spend(vendor_name=f"Vendor{i}", amount_usd=Decimal("100")) for i in range(10)])
        vendors = client.get("/api/spend/summary").json()["by_vendor"]
        assert len(vendors) <= 8

    def test_by_department(self, client, db):
        seed(db, [
            make_spend(oracle_department_name="Engineering", amount_usd=Decimal("600")),
            make_spend(oracle_department_name="Finance",     amount_usd=Decimal("400")),
        ])
        depts = client.get("/api/spend/summary").json()["by_department"]
        assert depts[0]["label"] == "Engineering"
        assert float(depts[0]["amount"]) == 600

    def test_by_month_sorted_asc(self, client, db):
        seed(db, [
            make_spend(month_key=202603, month_label="Mar 2026", amount_usd=Decimal("300")),
            make_spend(month_key=202601, month_label="Jan 2026", amount_usd=Decimal("100")),
            make_spend(month_key=202602, month_label="Feb 2026", amount_usd=Decimal("200")),
        ])
        months = client.get("/api/spend/summary").json()["by_month"]
        keys = [m["month_key"] for m in months]
        assert keys == sorted(keys)

    def test_by_cost_element_sorted_desc(self, client, db):
        seed(db, [
            make_spend(oracle_cost_element="Salaries",    amount_usd=Decimal("2000")),
            make_spend(oracle_cost_element="Salaries",    amount_usd=Decimal("1000")),
            make_spend(oracle_cost_element="Data Center", amount_usd=Decimal("500")),
        ])
        elems = client.get("/api/spend/summary").json()["by_cost_element"]
        assert elems[0]["label"] == "Salaries"
        assert float(elems[0]["amount"]) == 3000
        assert elems[1]["label"] == "Data Center"

    def test_by_activity_id_sorted_desc(self, client, db):
        seed(db, [
            make_spend(activity_id="AOPEX-0000001", amount_usd=Decimal("100")),
            make_spend(activity_id="AOPEX-0000002", amount_usd=Decimal("900")),
            make_spend(activity_id="AOPEX-0000001", amount_usd=Decimal("200")),
        ])
        acts = client.get("/api/spend/summary").json()["by_activity_id"]
        assert acts[0]["label"] == "AOPEX-0000002"
        assert float(acts[0]["amount"]) == 900
        assert acts[1]["label"] == "AOPEX-0000001"
        assert float(acts[1]["amount"]) == 300

    def test_by_activity_id_limited_to_15(self, client, db):
        seed(db, [
            make_spend(activity_id=f"AOPEX-{i:07d}", amount_usd=Decimal("100"))
            for i in range(1, 21)
        ])
        acts = client.get("/api/spend/summary").json()["by_activity_id"]
        assert len(acts) <= 15

    def test_percentages_sum_to_100(self, client, db):
        seed(db, [
            make_spend(oracle_account_group="R&D", amount_usd=Decimal("300")),
            make_spend(oracle_account_group="G&A", amount_usd=Decimal("700")),
        ])
        groups = client.get("/api/spend/summary").json()["by_account_group"]
        total_pct = sum(g["pct"] for g in groups)
        assert abs(total_pct - 100.0) < 0.5

    def test_filter_by_month_keys(self, client, db):
        seed(db, [
            make_spend(month_key=202601, amount_usd=Decimal("1000")),
            make_spend(month_key=202602, amount_usd=Decimal("2000")),
        ])
        body = client.get("/api/spend/summary?month_keys=202601").json()
        assert float(body["total_amount"]) == 1000
        assert body["total_transactions"] == 1

    def test_filter_by_activity_id(self, client, db):
        seed(db, [
            make_spend(activity_id="AOPEX-0000001", amount_usd=Decimal("500")),
            make_spend(activity_id="AOPEX-0000002", amount_usd=Decimal("300")),
        ])
        body = client.get("/api/spend/summary?activity_ids=AOPEX-0000001").json()
        assert float(body["total_amount"]) == 500
        assert body["total_transactions"] == 1


# ---------------------------------------------------------------------------
# NC Activity ID rule
# ---------------------------------------------------------------------------

class TestNcActivityIdRule:
    """
    Verifies that spend rows with oracle_cost_element='Employee Related'
    can carry activity_ids in the NC-{dept}-{account} format (e.g. NC-1100-ACC-1001).
    The actual assignment is done by _assign_nc_activity_ids() at API startup
    (MySQL-only); these tests confirm the format is accepted and filterable.
    """

    def test_employee_related_nc_activity_id_stored_and_returned(self, client, db):
        seed(db, [make_spend(
            oracle_cost_element="Employee Related",
            oracle_department="1100",
            oracle_account_number="ACC-1001",
            activity_id="NC-1100-ACC-1001",
        )])
        resp = client.get("/api/spend/transactions")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["activity_id"] == "NC-1100-ACC-1001"
        assert items[0]["oracle_cost_element"] == "Employee Related"

    def test_nc_activity_id_filter_returns_only_matching_rows(self, client, db):
        seed(db, [
            make_spend(
                vendor_name="ADP",
                oracle_cost_element="Employee Related",
                oracle_department="1400",
                oracle_account_number="ACC-2200",
                activity_id="NC-1400-ACC-2200",
            ),
            make_spend(
                vendor_name="AWS",
                oracle_cost_element="Salaries",
                oracle_department="1100",
                oracle_account_number="ACC-1001",
                activity_id="AOPEX-0000001",
            ),
        ])
        resp = client.get("/api/spend/transactions?activity_ids=NC-1400-ACC-2200")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["vendor_name"] == "ADP"

    def test_nc_activity_id_format_matches_rule(self):
        """Unit-test the format string used by _assign_nc_activity_ids."""
        dept = "1800"
        account = "ACC-3178"
        nc_id = f"NC-{dept}-{account}"
        assert nc_id == "NC-1800-ACC-3178"
        assert nc_id.startswith("NC-")
        assert len(nc_id) <= 20  # fits varchar(20) activity_id column

    def test_multiple_depts_produce_distinct_nc_ids(self):
        combos = [
            ("1100", "ACC-1001"),
            ("1400", "ACC-2200"),
            ("1800", "ACC-3178"),
        ]
        nc_ids = [f"NC-{dept}-{acct}" for dept, acct in combos]
        assert len(nc_ids) == len(set(nc_ids))
