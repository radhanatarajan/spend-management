"""
Tests for the Contract Database module.

Covers:
  - compute_monthly_amount  (unit)
  - _is_multi_year          (unit)
  - GET/POST/PUT/DELETE /api/contracts
  - POST/PUT/DELETE /api/contracts/{id}/lines
  - GET /api/contracts/report
"""
from datetime import date
from decimal import Decimal

import pytest

from src.models.contract import BillingInterval, ContractStatus
from src.schemas.contract import compute_monthly_amount, fiscal_year_months, month_to_fy
from tests.conftest import make_contract


# ── Shared line fixtures ───────────────────────────────────────────────────────

LINE_Y1 = dict(
    po_line_number=1,
    period_start=date(2026, 1, 1),
    period_end=date(2026, 12, 31),
    billing_interval=BillingInterval.MONTHLY,
    entered_amount=Decimal("1000.00"),
)
LINE_Y2 = dict(
    po_line_number=2,
    period_start=date(2027, 1, 1),
    period_end=date(2027, 12, 31),
    billing_interval=BillingInterval.MONTHLY,
    entered_amount=Decimal("1100.00"),
)
LINE_Y3 = dict(
    po_line_number=3,
    period_start=date(2028, 1, 1),
    period_end=date(2028, 12, 31),
    billing_interval=BillingInterval.MONTHLY,
    entered_amount=Decimal("1200.00"),
)
# Line with a gap (starts Feb 2027 instead of Jan 2027)
LINE_GAP = dict(
    po_line_number=2,
    period_start=date(2027, 2, 1),
    period_end=date(2027, 12, 31),
    billing_interval=BillingInterval.MONTHLY,
    entered_amount=Decimal("1100.00"),
)


# ══════════════════════════════════════════════════════════════════════════════
# Unit: compute_monthly_amount
# ══════════════════════════════════════════════════════════════════════════════

class TestComputeMonthlyAmount:
    def test_monthly_returns_as_is(self):
        result = compute_monthly_amount(
            Decimal("500.00"), BillingInterval.MONTHLY,
            date(2026, 1, 1), date(2026, 12, 31),
        )
        assert result == Decimal("500.00")

    def test_quarterly_divides_by_3(self):
        result = compute_monthly_amount(
            Decimal("3000.00"), BillingInterval.QUARTERLY,
            date(2026, 1, 1), date(2026, 3, 31),
        )
        assert result == Decimal("1000.00")

    def test_yearly_divides_by_12(self):
        result = compute_monthly_amount(
            Decimal("12000.00"), BillingInterval.YEARLY,
            date(2026, 1, 1), date(2026, 12, 31),
        )
        assert result == Decimal("1000.00")

    def test_custom_divides_by_months_in_period(self):
        # Jan–Mar = 3 months
        result = compute_monthly_amount(
            Decimal("3000.00"), BillingInterval.CUSTOM,
            date(2026, 1, 1), date(2026, 3, 31),
        )
        assert result == Decimal("1000.00")

    def test_custom_18_month_period(self):
        result = compute_monthly_amount(
            Decimal("18000.00"), BillingInterval.CUSTOM,
            date(2026, 1, 1), date(2027, 6, 30),
        )
        assert result == Decimal("1000.00")

    def test_quarterly_rounds_to_cents(self):
        # 100 / 3 = 33.333… → 33.33
        result = compute_monthly_amount(
            Decimal("100.00"), BillingInterval.QUARTERLY,
            date(2026, 1, 1), date(2026, 3, 31),
        )
        assert result == Decimal("33.33")


# ══════════════════════════════════════════════════════════════════════════════
# Unit: fiscal year helpers
# ══════════════════════════════════════════════════════════════════════════════

class TestFiscalYearHelpers:
    def test_month_to_fy_is_calendar_year(self):
        assert month_to_fy(2027, 6) == 2027

    def test_fiscal_year_months_jan_to_dec(self):
        months = fiscal_year_months(2027)
        assert months[0] == (2027, 1)
        assert months[-1] == (2027, 12)
        assert len(months) == 12


# ══════════════════════════════════════════════════════════════════════════════
# Unit: _is_multi_year (via report endpoint behaviour)
# The logic is also exercised indirectly through the report tests below.
# ══════════════════════════════════════════════════════════════════════════════

class TestIsMultiYear:
    """Test multi-year detection by inspecting what the report endpoint includes."""

    def test_single_line_appears_but_not_flagged_multi_year(self, client, db):
        make_contract(db, lines=[LINE_Y1])
        resp = client.get("/api/contracts/report?fiscal_year=2026")
        assert resp.status_code == 200
        rows = resp.json()["rows"]
        assert len(rows) == 1
        assert rows[0]["is_multi_year"] is False

    def test_two_consecutive_lines_flagged_multi_year(self, client, db):
        make_contract(db, lines=[LINE_Y1, LINE_Y2])
        resp = client.get("/api/contracts/report?fiscal_year=2026")
        assert resp.status_code == 200
        rows = resp.json()["rows"]
        assert len(rows) == 1
        assert rows[0]["is_multi_year"] is True

    def test_gap_between_lines_not_flagged_multi_year(self, client, db):
        make_contract(db, lines=[LINE_Y1, LINE_GAP])
        resp = client.get("/api/contracts/report?fiscal_year=2026")
        rows = resp.json()["rows"]
        assert len(rows) == 1
        assert rows[0]["is_multi_year"] is False

    def test_three_consecutive_lines_is_multi_year(self, client, db):
        make_contract(db, lines=[LINE_Y1, LINE_Y2, LINE_Y3])
        resp = client.get("/api/contracts/report?fiscal_year=2026")
        assert len(resp.json()["rows"]) == 1

    def test_december_to_january_rollover(self, client, db):
        # Dec end → Jan start is valid consecutive
        line_dec = dict(
            po_line_number=1,
            period_start=date(2026, 1, 1), period_end=date(2026, 12, 31),
            billing_interval=BillingInterval.MONTHLY, entered_amount=Decimal("500.00"),
        )
        line_jan = dict(
            po_line_number=2,
            period_start=date(2027, 1, 1), period_end=date(2027, 12, 31),
            billing_interval=BillingInterval.MONTHLY, entered_amount=Decimal("550.00"),
        )
        make_contract(db, lines=[line_dec, line_jan])
        resp = client.get("/api/contracts/report?fiscal_year=2026")
        assert len(resp.json()["rows"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/contracts
# ══════════════════════════════════════════════════════════════════════════════

class TestListContracts:
    def test_empty_returns_empty_list(self, client):
        resp = client.get("/api/contracts")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_all_contracts(self, client, db):
        make_contract(db, vendor="Zoom")
        make_contract(db, vendor="Slack", po="PO-002")
        resp = client.get("/api/contracts")
        assert resp.status_code == 200
        assert len(resp.json()) == 2

    def test_response_includes_lines(self, client, db):
        make_contract(db, lines=[LINE_Y1])
        contracts = client.get("/api/contracts").json()
        assert len(contracts[0]["lines"]) == 1

    def test_ordered_by_vendor_name(self, client, db):
        make_contract(db, vendor="Zoom", po="PO-Z")
        make_contract(db, vendor="Acme", po="PO-A")
        names = [c["vendor_name"] for c in client.get("/api/contracts").json()]
        assert names == sorted(names)


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/contracts
# ══════════════════════════════════════════════════════════════════════════════

class TestCreateContract:
    def _payload(self, **overrides):
        base = dict(
            vendor_name="GitHub",
            oracle_department="1100",
            oracle_department_name="Engineering",
            oracle_account_number="ACC-6401",
            oracle_account_sub_group="Software Licenses",
            purchase_order_number="PO-91200",
            status="active",
            lines=[],
        )
        base.update(overrides)
        return base

    def test_create_minimal_contract(self, admin_client):
        resp = admin_client.post("/api/contracts", json=self._payload())
        assert resp.status_code == 201
        body = resp.json()
        assert body["vendor_name"] == "GitHub"
        assert body["lines"] == []

    def test_create_with_monthly_line(self, admin_client):
        lines = [dict(
            po_line_number=1,
            period_start="2026-01-01", period_end="2026-12-31",
            billing_interval="monthly", entered_amount="1000.00",
        )]
        resp = admin_client.post("/api/contracts", json=self._payload(lines=lines))
        assert resp.status_code == 201
        line = resp.json()["lines"][0]
        assert float(line["monthly_amount"]) == 1000.00
        assert float(line["entered_amount"]) == 1000.00

    def test_create_with_quarterly_line_computes_monthly(self, admin_client):
        lines = [dict(
            po_line_number=1,
            period_start="2026-01-01", period_end="2026-03-31",
            billing_interval="quarterly", entered_amount="3000.00",
        )]
        resp = admin_client.post("/api/contracts", json=self._payload(lines=lines))
        assert resp.status_code == 201
        line = resp.json()["lines"][0]
        assert float(line["monthly_amount"]) == 1000.00
        assert float(line["entered_amount"]) == 3000.00

    def test_create_with_yearly_line_computes_monthly(self, admin_client):
        lines = [dict(
            po_line_number=1,
            period_start="2026-01-01", period_end="2026-12-31",
            billing_interval="yearly", entered_amount="12000.00",
        )]
        resp = admin_client.post("/api/contracts", json=self._payload(lines=lines))
        line = resp.json()["lines"][0]
        assert float(line["monthly_amount"]) == 1000.00

    def test_create_with_custom_line_computes_monthly(self, admin_client):
        # 6-month period, total 6000 → 1000/mo
        lines = [dict(
            po_line_number=1,
            period_start="2026-01-01", period_end="2026-06-30",
            billing_interval="custom", entered_amount="6000.00",
        )]
        resp = admin_client.post("/api/contracts", json=self._payload(lines=lines))
        line = resp.json()["lines"][0]
        assert float(line["monthly_amount"]) == 1000.00

    def test_computed_total_amount_on_line(self, admin_client):
        # monthly 500 × 12 months = 6000
        lines = [dict(
            po_line_number=1,
            period_start="2026-01-01", period_end="2026-12-31",
            billing_interval="monthly", entered_amount="500.00",
        )]
        resp = admin_client.post("/api/contracts", json=self._payload(lines=lines))
        line = resp.json()["lines"][0]
        assert float(line["total_amount"]) == 6000.00
        assert line["months_in_period"] == 12

    def test_contract_total_sums_lines(self, admin_client):
        lines = [
            dict(po_line_number=1, period_start="2026-01-01", period_end="2026-12-31",
                 billing_interval="monthly", entered_amount="1000.00"),
            dict(po_line_number=2, period_start="2027-01-01", period_end="2027-12-31",
                 billing_interval="monthly", entered_amount="1100.00"),
        ]
        body = admin_client.post("/api/contracts", json=self._payload(lines=lines)).json()
        # 1000×12 + 1100×12 = 12000 + 13200 = 25200
        assert float(body["contract_total"]) == 25200.00

    def test_missing_required_field_returns_422(self, admin_client):
        payload = self._payload()
        del payload["vendor_name"]
        resp = admin_client.post("/api/contracts", json=payload)
        assert resp.status_code == 422


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/contracts/{id}
# ══════════════════════════════════════════════════════════════════════════════

class TestGetContract:
    def test_returns_contract(self, client, db):
        c = make_contract(db, vendor="Notion")
        resp = client.get(f"/api/contracts/{c.id}")
        assert resp.status_code == 200
        assert resp.json()["vendor_name"] == "Notion"

    def test_404_for_missing_contract(self, client):
        resp = client.get("/api/contracts/9999")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# PUT /api/contracts/{id}
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateContract:
    def test_update_vendor_name(self, admin_client, db):
        c = make_contract(db, vendor="OldName")
        resp = admin_client.put(f"/api/contracts/{c.id}", json={"vendor_name": "NewName"})
        assert resp.status_code == 200
        assert resp.json()["vendor_name"] == "NewName"

    def test_update_status(self, admin_client, db):
        c = make_contract(db)
        resp = admin_client.put(f"/api/contracts/{c.id}", json={"status": "expired"})
        assert resp.json()["status"] == "expired"

    def test_partial_update_preserves_other_fields(self, admin_client, db):
        c = make_contract(db, vendor="Figma")
        admin_client.put(f"/api/contracts/{c.id}", json={"status": "pending"})
        body = admin_client.get(f"/api/contracts/{c.id}").json()
        assert body["vendor_name"] == "Figma"
        assert body["status"] == "pending"

    def test_update_nonexistent_returns_404(self, admin_client):
        resp = admin_client.put("/api/contracts/9999", json={"vendor_name": "X"})
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/contracts/{id}
# ══════════════════════════════════════════════════════════════════════════════

class TestDeleteContract:
    def test_delete_returns_204(self, admin_client, db):
        c = make_contract(db)
        resp = admin_client.delete(f"/api/contracts/{c.id}")
        assert resp.status_code == 204

    def test_deleted_contract_no_longer_exists(self, admin_client, db):
        c = make_contract(db)
        admin_client.delete(f"/api/contracts/{c.id}")
        assert admin_client.get(f"/api/contracts/{c.id}").status_code == 404

    def test_delete_nonexistent_returns_404(self, admin_client):
        assert admin_client.delete("/api/contracts/9999").status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# POST /api/contracts/{id}/lines
# ══════════════════════════════════════════════════════════════════════════════

class TestAddLine:
    def _line_payload(self, **overrides):
        base = dict(
            po_line_number=1,
            period_start="2026-01-01",
            period_end="2026-12-31",
            billing_interval="monthly",
            entered_amount="800.00",
        )
        base.update(overrides)
        return base

    def test_add_line_returns_201(self, admin_client, db):
        c = make_contract(db)
        resp = admin_client.post(f"/api/contracts/{c.id}/lines", json=self._line_payload())
        assert resp.status_code == 201

    def test_add_line_computes_monthly_amount(self, admin_client, db):
        c = make_contract(db)
        resp = admin_client.post(f"/api/contracts/{c.id}/lines",
                                 json=self._line_payload(billing_interval="yearly", entered_amount="12000.00"))
        assert float(resp.json()["monthly_amount"]) == 1000.00

    def test_add_line_to_missing_contract_404(self, admin_client):
        resp = admin_client.post("/api/contracts/9999/lines", json=self._line_payload())
        assert resp.status_code == 404

    def test_line_appears_in_contract(self, admin_client, db):
        c = make_contract(db)
        admin_client.post(f"/api/contracts/{c.id}/lines", json=self._line_payload())
        body = admin_client.get(f"/api/contracts/{c.id}").json()
        assert len(body["lines"]) == 1


# ══════════════════════════════════════════════════════════════════════════════
# PUT /api/contracts/{id}/lines/{line_id}
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateLine:
    def test_update_amount_recomputes_monthly(self, admin_client, db):
        c = make_contract(db, lines=[LINE_Y1])
        line_id = admin_client.get(f"/api/contracts/{c.id}").json()["lines"][0]["id"]
        resp = admin_client.put(f"/api/contracts/{c.id}/lines/{line_id}",
                                json={"entered_amount": "2000.00", "billing_interval": "monthly"})
        assert resp.status_code == 200
        assert float(resp.json()["monthly_amount"]) == 2000.00

    def test_update_interval_recomputes_monthly(self, admin_client, db):
        # Start monthly at 3000, switch to quarterly → 3000/3 = 1000/mo
        c = make_contract(db, lines=[{**LINE_Y1, "entered_amount": Decimal("3000.00")}])
        line_id = admin_client.get(f"/api/contracts/{c.id}").json()["lines"][0]["id"]
        resp = admin_client.put(f"/api/contracts/{c.id}/lines/{line_id}",
                                json={"billing_interval": "quarterly"})
        assert float(resp.json()["monthly_amount"]) == 1000.00

    def test_update_period_dates(self, admin_client, db):
        c = make_contract(db, lines=[LINE_Y1])
        line_id = admin_client.get(f"/api/contracts/{c.id}").json()["lines"][0]["id"]
        resp = admin_client.put(f"/api/contracts/{c.id}/lines/{line_id}",
                                json={"period_end": "2026-06-30"})
        assert resp.status_code == 200
        assert resp.json()["period_end"] == "2026-06-30"

    def test_update_wrong_contract_returns_404(self, admin_client, db):
        c1 = make_contract(db, po="PO-A", lines=[LINE_Y1])
        c2 = make_contract(db, po="PO-B")
        line_id = admin_client.get(f"/api/contracts/{c1.id}").json()["lines"][0]["id"]
        # Try to update c1's line through c2's URL
        resp = admin_client.put(f"/api/contracts/{c2.id}/lines/{line_id}",
                                json={"entered_amount": "999.00"})
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# DELETE /api/contracts/{id}/lines/{line_id}
# ══════════════════════════════════════════════════════════════════════════════

class TestDeleteLine:
    def test_delete_line_returns_204(self, admin_client, db):
        c = make_contract(db, lines=[LINE_Y1])
        line_id = admin_client.get(f"/api/contracts/{c.id}").json()["lines"][0]["id"]
        resp = admin_client.delete(f"/api/contracts/{c.id}/lines/{line_id}")
        assert resp.status_code == 204

    def test_deleted_line_not_in_contract(self, admin_client, db):
        c = make_contract(db, lines=[LINE_Y1])
        line_id = admin_client.get(f"/api/contracts/{c.id}").json()["lines"][0]["id"]
        admin_client.delete(f"/api/contracts/{c.id}/lines/{line_id}")
        assert admin_client.get(f"/api/contracts/{c.id}").json()["lines"] == []

    def test_delete_missing_line_returns_404(self, admin_client, db):
        c = make_contract(db)
        resp = admin_client.delete(f"/api/contracts/{c.id}/lines/9999")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# GET /api/contracts/report
# ══════════════════════════════════════════════════════════════════════════════

class TestContractReport:
    def test_missing_fiscal_year_returns_422(self, client):
        resp = client.get("/api/contracts/report")
        assert resp.status_code == 422

    def test_empty_db_returns_empty_rows(self, client):
        resp = client.get("/api/contracts/report?fiscal_year=2026")
        assert resp.status_code == 200
        body = resp.json()
        assert body["rows"] == []
        assert body["fiscal_year"] == 2026
        assert len(body["month_keys"]) == 12

    def test_month_keys_span_full_calendar_year(self, client):
        resp = client.get("/api/contracts/report?fiscal_year=2027")
        keys = resp.json()["month_keys"]
        assert keys[0] == "2027-01"
        assert keys[-1] == "2027-12"

    def test_actual_amounts_for_covered_months(self, client, db):
        # LINE_Y1 covers all of 2026; both lines make it multi-year
        make_contract(db, lines=[LINE_Y1, LINE_Y2])
        body = client.get("/api/contracts/report?fiscal_year=2026").json()
        row = body["rows"][0]
        assert float(row["monthly_amounts"]["2026-06"]) == 1000.00
        assert row["monthly_assumed"]["2026-06"] is False

    def test_renewal_assumption_for_months_beyond_last_line(self, client, db):
        # LINE_Y1 ends Dec-2026, LINE_Y2 ends Dec-2027.
        # Report for FY2028 → all 12 months are assumed at LINE_Y2's rate (1100/mo).
        make_contract(db, lines=[LINE_Y1, LINE_Y2])
        body = client.get("/api/contracts/report?fiscal_year=2028").json()
        row = body["rows"][0]
        assert float(row["monthly_amounts"]["2028-01"]) == 1100.00
        assert row["monthly_assumed"]["2028-01"] is True

    def test_assumed_total_equals_sum_of_assumed_months(self, client, db):
        make_contract(db, lines=[LINE_Y1, LINE_Y2])
        body = client.get("/api/contracts/report?fiscal_year=2028").json()
        row = body["rows"][0]
        expected = 1100.00 * 12
        assert abs(float(row["assumed_total"]) - expected) < 0.01

    def test_months_before_contract_start_are_excluded(self, client, db):
        # Contract starts Jan-2026; report for FY2025 → no coverage, no assumption → excluded
        make_contract(db, lines=[LINE_Y1, LINE_Y2])
        body = client.get("/api/contracts/report?fiscal_year=2025").json()
        assert body["rows"] == []

    def test_fy_total_is_sum_of_monthly_amounts(self, client, db):
        make_contract(db, lines=[LINE_Y1, LINE_Y2])
        body = client.get("/api/contracts/report?fiscal_year=2026").json()
        row = body["rows"][0]
        # 12 months × 1000 = 12000
        assert float(row["fiscal_year_total"]) == 12000.00

    def test_monthly_totals_footer_matches_rows(self, client, db):
        make_contract(db, lines=[LINE_Y1, LINE_Y2])
        body = client.get("/api/contracts/report?fiscal_year=2026").json()
        for key in body["month_keys"]:
            row_sum = sum(float(r["monthly_amounts"][key]) for r in body["rows"]
                          if r["monthly_amounts"].get(key) is not None)
            assert abs(row_sum - float(body["monthly_totals"][key])) < 0.01

    def test_grand_total_sums_all_fy_totals(self, client, db):
        make_contract(db, vendor="A", po="PO-A", lines=[LINE_Y1, LINE_Y2])
        make_contract(db, vendor="B", po="PO-B", lines=[LINE_Y1, LINE_Y2])
        body = client.get("/api/contracts/report?fiscal_year=2026").json()
        expected = sum(float(r["fiscal_year_total"]) for r in body["rows"])
        assert abs(float(body["grand_total"]) - expected) < 0.01

    def test_available_fiscal_years_includes_line_years(self, client, db):
        make_contract(db, lines=[LINE_Y1, LINE_Y2])
        body = client.get("/api/contracts/report?fiscal_year=2026").json()
        assert 2026 in body["available_fiscal_years"]
        assert 2027 in body["available_fiscal_years"]

    def test_filter_options_populated(self, client, db):
        make_contract(db, vendor="Zoom", po="PO-Z", lines=[LINE_Y1, LINE_Y2])
        body = client.get("/api/contracts/report?fiscal_year=2026").json()
        opts = body["filter_options"]
        assert "Zoom" in opts["vendors"]
        assert "active" in opts["statuses"]
        # GL dimension keys always present (may be empty if no matching account_numbers rows)
        assert "account_groups" in opts
        assert "account_sub_groups" in opts
        assert "cost_elements" in opts

    def test_report_row_has_gl_dimension_fields(self, client, db):
        make_contract(db, vendor="Zoom", po="PO-Z", lines=[LINE_Y1, LINE_Y2])
        rows = client.get("/api/contracts/report?fiscal_year=2026").json()["rows"]
        assert len(rows) == 1
        row = rows[0]
        assert "account_group" in row
        assert "account_sub_group" in row
        assert "cost_element" in row
        # No AccountNumber seed in test DB — fields fall back to empty string
        assert isinstance(row["account_group"], str)
        assert isinstance(row["account_sub_group"], str)
        assert isinstance(row["cost_element"], str)

    def test_cross_contract_grouping_detected_as_multi_year(self, client, db):
        # Two separate Contract DB records, same vendor+dept+account+PO, consecutive lines.
        # Each record has only 1 line — multi-year only detectable via grouping.
        line1 = dict(
            po_line_number=1,
            period_start=date(2026, 5, 1), period_end=date(2027, 4, 30),
            billing_interval=BillingInterval.MONTHLY, entered_amount=Decimal("10000.00"),
        )
        line2 = dict(
            po_line_number=2,
            period_start=date(2027, 5, 1), period_end=date(2028, 4, 30),
            billing_interval=BillingInterval.MONTHLY, entered_amount=Decimal("11000.00"),
        )
        make_contract(db, vendor="Zoom", po="PO-ZM", lines=[line1])
        make_contract(db, vendor="Zoom", po="PO-ZM", lines=[line2])
        body = client.get("/api/contracts/report?fiscal_year=2027").json()
        assert len(body["rows"]) == 1
        row = body["rows"][0]
        assert row["vendor_name"] == "Zoom"
        assert row["num_lines"] == 2
        # Jan-Apr 2027 covered by line1 at 10000; May-Dec 2027 covered by line2 at 11000
        assert float(row["monthly_amounts"]["2027-01"]) == 10000.00
        assert float(row["monthly_amounts"]["2027-06"]) == 11000.00
        assert row["monthly_assumed"]["2027-06"] is False

    def test_partial_year_coverage_mixed_null_and_amounts(self, client, db):
        # LINE_Y1 starts Jan-2026; report for FY2026 covers full year → no nulls
        # but a contract starting mid-year should have nulls for earlier months
        line_mid = dict(
            po_line_number=1,
            period_start=date(2026, 7, 1), period_end=date(2026, 12, 31),
            billing_interval=BillingInterval.MONTHLY, entered_amount=Decimal("500.00"),
        )
        line_next = dict(
            po_line_number=2,
            period_start=date(2027, 1, 1), period_end=date(2027, 12, 31),
            billing_interval=BillingInterval.MONTHLY, entered_amount=Decimal("550.00"),
        )
        make_contract(db, lines=[line_mid, line_next])
        body = client.get("/api/contracts/report?fiscal_year=2026").json()
        row = body["rows"][0]
        # Jan–Jun 2026: before contract start → null
        assert row["monthly_amounts"]["2026-01"] is None
        assert row["monthly_assumed"]["2026-01"] is False
        # Jul–Dec 2026: covered
        assert float(row["monthly_amounts"]["2026-07"]) == 500.00
        assert row["monthly_assumed"]["2026-07"] is False


# ══════════════════════════════════════════════════════════════════════════════
# Contract Audit
# ══════════════════════════════════════════════════════════════════════════════

class TestContractAudit:
    def _contract_payload(self, **overrides):
        base = dict(
            vendor_name="Adobe",
            oracle_department="1100",
            oracle_department_name="Engineering",
            oracle_account_number="ACC-1234",
            oracle_account_sub_group="Software",
            purchase_order_number="PO-ADO-001",
            status="active",
        )
        base.update(overrides)
        return base

    def test_create_contract_logged(self, admin_client):
        r = admin_client.post("/api/contracts", json=self._contract_payload())
        assert r.status_code == 201
        contract_id = r.json()["id"]

        audit = admin_client.get(f"/api/contracts/audit?contract_id={contract_id}").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "CREATED"
        assert audit[0]["changes"] == {}

    def test_update_contract_logged(self, admin_client, db):
        c = make_contract(db, vendor="OldCo")
        admin_client.put(f"/api/contracts/{c.id}", json={"vendor_name": "NewCo"})

        audit = admin_client.get(f"/api/contracts/audit?contract_id={c.id}").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "UPDATED"
        assert audit[0]["changes"]["vendor_name"]["old"] == "OldCo"
        assert audit[0]["changes"]["vendor_name"]["new"] == "NewCo"

    def test_update_no_change_no_audit(self, admin_client, db):
        c = make_contract(db, vendor="Same")
        admin_client.put(f"/api/contracts/{c.id}", json={"vendor_name": "Same"})
        audit = admin_client.get(f"/api/contracts/audit?contract_id={c.id}").json()
        assert len(audit) == 0

    def test_delete_contract_logged(self, admin_client, db):
        c = make_contract(db, vendor="Doomed")
        contract_id = c.id
        r = admin_client.delete(f"/api/contracts/{contract_id}")
        assert r.status_code == 204

        audit = admin_client.get(f"/api/contracts/audit?contract_id={contract_id}").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "DELETED"

    def test_audit_filter_by_vendor(self, admin_client, db):
        c1 = make_contract(db, vendor="Acme", po="PO-A")
        c2 = make_contract(db, vendor="Beta", po="PO-B")
        admin_client.put(f"/api/contracts/{c1.id}", json={"status": "expired"})
        admin_client.put(f"/api/contracts/{c2.id}", json={"status": "expired"})

        audit = admin_client.get("/api/contracts/audit?vendor_name=Acme").json()
        assert len(audit) == 1
        assert audit[0]["vendor_name"] == "Acme"

    def test_audit_requires_auth(self, client):
        r = client.get("/api/contracts/audit")
        assert r.status_code == 401

    def test_readonly_can_view_audit(self, readonly_client, admin_client, db):
        c = make_contract(db)
        admin_client.put(f"/api/contracts/{c.id}", json={"status": "expired"})
        r = readonly_client.get(f"/api/contracts/audit?contract_id={c.id}")
        assert r.status_code == 200
        assert len(r.json()) == 1

    # ── Contract line audit ────────────────────────────────────────────────────

    def test_add_line_logged(self, admin_client, db):
        c = make_contract(db)
        line_payload = dict(
            po_line_number=1, period_start="2026-01-01", period_end="2026-12-31",
            billing_interval="monthly", entered_amount="1000.00",
        )
        r = admin_client.post(f"/api/contracts/{c.id}/lines", json=line_payload)
        assert r.status_code == 201

        audit = admin_client.get(f"/api/contracts/lines/audit?contract_id={c.id}").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "CREATED"
        assert audit[0]["po_line_number"] == 1

    def test_update_line_logged(self, admin_client, db):
        c = make_contract(db, lines=[LINE_Y1])
        line_id = admin_client.get(f"/api/contracts/{c.id}").json()["lines"][0]["id"]
        admin_client.put(f"/api/contracts/{c.id}/lines/{line_id}",
                         json={"entered_amount": "2000.00", "billing_interval": "monthly"})

        audit = admin_client.get(f"/api/contracts/lines/audit?contract_id={c.id}").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "UPDATED"
        assert audit[0]["changes"]["entered_amount"]["old"] == "1000.00"
        assert audit[0]["changes"]["entered_amount"]["new"] == "2000.00"

    def test_update_line_no_change_no_audit(self, admin_client, db):
        c = make_contract(db, lines=[LINE_Y1])
        line_id = admin_client.get(f"/api/contracts/{c.id}").json()["lines"][0]["id"]
        admin_client.put(f"/api/contracts/{c.id}/lines/{line_id}",
                         json={"billing_interval": "monthly"})
        audit = admin_client.get(f"/api/contracts/lines/audit?contract_id={c.id}").json()
        assert len(audit) == 0

    def test_delete_line_logged(self, admin_client, db):
        c = make_contract(db, lines=[LINE_Y1])
        line_id = admin_client.get(f"/api/contracts/{c.id}").json()["lines"][0]["id"]
        admin_client.delete(f"/api/contracts/{c.id}/lines/{line_id}")

        audit = admin_client.get(f"/api/contracts/lines/audit?contract_id={c.id}").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "DELETED"

    def test_lines_audit_filter_by_line_id(self, admin_client, db):
        c = make_contract(db, lines=[LINE_Y1, LINE_Y2])
        lines = admin_client.get(f"/api/contracts/{c.id}").json()["lines"]
        line_id = lines[0]["id"]
        admin_client.put(f"/api/contracts/{c.id}/lines/{line_id}",
                         json={"entered_amount": "1500.00", "billing_interval": "monthly"})
        admin_client.put(f"/api/contracts/{c.id}/lines/{lines[1]['id']}",
                         json={"entered_amount": "1600.00", "billing_interval": "monthly"})

        audit = admin_client.get(f"/api/contracts/lines/audit?contract_line_id={line_id}").json()
        assert len(audit) == 1
        assert audit[0]["changes"]["entered_amount"]["new"] == "1500.00"

    def test_lines_audit_requires_auth(self, client):
        assert client.get("/api/contracts/lines/audit").status_code == 401

    def test_contract_audit_has_no_line_events(self, admin_client, db):
        c = make_contract(db)
        admin_client.post(f"/api/contracts/{c.id}/lines", json=dict(
            po_line_number=1, period_start="2026-01-01", period_end="2026-12-31",
            billing_interval="monthly", entered_amount="500.00",
        ))
        # contract_audit should be empty — line event went to contract_lines_audit
        assert admin_client.get(f"/api/contracts/audit?contract_id={c.id}").json() == []


# ══════════════════════════════════════════════════════════════════════════════
# Contract Change Log (reports/audit — unified contract + line events)
# ══════════════════════════════════════════════════════════════════════════════

class TestContractAuditReport:
    _LINE = dict(
        po_line_number=1, period_start="2026-01-01", period_end="2026-12-31",
        billing_interval="monthly", entered_amount="1000.00",
    )
    _CONTRACT = dict(
        vendor_name="Contoso",
        oracle_department="1100",
        oracle_department_name="Engineering",
        oracle_account_number="ACC-9999",
        oracle_account_sub_group="SaaS",
        purchase_order_number="PO-C-001",
        status="active",
    )

    def test_returns_empty_when_no_events(self, admin_client):
        r = admin_client.get("/api/contracts/reports/audit")
        assert r.status_code == 200
        body = r.json()
        assert body["rows"] == []
        assert set(body["filter_options"].keys()) == {"vendors", "event_types", "entity_types", "users"}

    def test_includes_contract_events(self, admin_client):
        admin_client.post("/api/contracts", json=self._CONTRACT)
        r = admin_client.get("/api/contracts/reports/audit")
        assert r.status_code == 200
        rows = r.json()["rows"]
        assert len(rows) >= 1
        assert any(row["entity_type"] == "Contract" for row in rows)

    def test_includes_line_events(self, admin_client, db):
        c = make_contract(db)
        admin_client.post(f"/api/contracts/{c.id}/lines", json=self._LINE)
        r = admin_client.get("/api/contracts/reports/audit")
        rows = r.json()["rows"]
        assert any(row["entity_type"] == "Line" for row in rows)

    def test_entity_type_for_contract_vs_line(self, admin_client, db):
        c = make_contract(db)
        admin_client.put(f"/api/contracts/{c.id}", json={"status": "expired"})
        admin_client.post(f"/api/contracts/{c.id}/lines", json=self._LINE)
        rows = admin_client.get("/api/contracts/reports/audit").json()["rows"]
        entity_types = {row["entity_type"] for row in rows}
        assert "Contract" in entity_types
        assert "Line" in entity_types

    def test_po_line_number_present_on_line_events(self, admin_client, db):
        c = make_contract(db)
        admin_client.post(f"/api/contracts/{c.id}/lines", json=self._LINE)
        rows = admin_client.get("/api/contracts/reports/audit").json()["rows"]
        line_rows = [r for r in rows if r["entity_type"] == "Line"]
        assert len(line_rows) == 1
        assert line_rows[0]["po_line_number"] == 1

    def test_po_line_number_null_on_contract_events(self, admin_client):
        admin_client.post("/api/contracts", json=self._CONTRACT)
        rows = admin_client.get("/api/contracts/reports/audit").json()["rows"]
        contract_rows = [r for r in rows if r["entity_type"] == "Contract"]
        assert all(r["po_line_number"] is None for r in contract_rows)

    def test_sorted_newest_first(self, admin_client, db):
        c = make_contract(db)
        admin_client.put(f"/api/contracts/{c.id}", json={"status": "expired"})
        admin_client.post(f"/api/contracts/{c.id}/lines", json=self._LINE)
        rows = admin_client.get("/api/contracts/reports/audit").json()["rows"]
        timestamps = [r["changed_at"] for r in rows]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_filter_options_populated_after_events(self, admin_client):
        admin_client.post("/api/contracts", json=self._CONTRACT)
        fo = admin_client.get("/api/contracts/reports/audit").json()["filter_options"]
        assert "Contoso" in fo["vendors"]
        assert "CREATED" in fo["event_types"]
        assert "Contract" in fo["entity_types"]

    def test_requires_auth(self, client):
        assert client.get("/api/contracts/reports/audit").status_code == 401
