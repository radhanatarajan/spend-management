"""
Tests for the Budget Planning module.

Covers:
  - GET/PUT /api/budget/config          (NC config)
  - GET/POST/PUT/DELETE /api/budget/scenarios
  - GET /api/budget/non-controllable    (plan with actuals + entries)
  - PUT /api/budget/entries             (upsert)
  - PATCH /api/budget/entries/{id}/status (status transitions)
  - DELETE /api/budget/entries/{id}
  - GET /api/budget/scenarios/{id}/audit
  - GET /api/budget/compare
  - ALLOWED_TRANSITIONS state machine
"""
from decimal import Decimal

import pytest

from src.models.budget import BudgetEntryAudit
from src.models.user import UserRole
from tests.conftest import make_scenario, make_entry, make_spend


# ══════════════════════════════════════════════════════════════════════════════
# NC Config
# ══════════════════════════════════════════════════════════════════════════════

class TestNcConfig:
    def test_get_creates_config_if_missing(self, admin_client):
        resp = admin_client.get("/api/budget/config?fiscal_year=2027")
        assert resp.status_code == 200
        body = resp.json()
        assert body["fiscal_year"] == 2027
        assert body["selected_cost_elements"] == []
        assert body["actuals_cutoff_month_key"] is None

    def test_get_returns_existing(self, admin_client):
        admin_client.get("/api/budget/config?fiscal_year=2027")  # creates it
        resp = admin_client.get("/api/budget/config?fiscal_year=2027")
        assert resp.status_code == 200
        assert resp.json()["fiscal_year"] == 2027

    def test_put_updates_cost_elements(self, bizadmin_client):
        resp = bizadmin_client.put("/api/budget/config", json={
            "fiscal_year": 2027,
            "selected_cost_elements": ["Salaries", "Travel"],
            "actuals_cutoff_month_key": None,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["selected_cost_elements"] == ["Salaries", "Travel"]

    def test_put_updates_actuals_cutoff(self, bizadmin_client):
        resp = bizadmin_client.put("/api/budget/config", json={
            "fiscal_year": 2027,
            "selected_cost_elements": [],
            "actuals_cutoff_month_key": 202606,
        })
        assert resp.status_code == 200
        assert resp.json()["actuals_cutoff_month_key"] == 202606

    def test_put_clears_cutoff_to_null(self, bizadmin_client):
        bizadmin_client.put("/api/budget/config", json={
            "fiscal_year": 2027,
            "selected_cost_elements": [],
            "actuals_cutoff_month_key": 202606,
        })
        resp = bizadmin_client.put("/api/budget/config", json={
            "fiscal_year": 2027,
            "selected_cost_elements": [],
            "actuals_cutoff_month_key": None,
        })
        assert resp.json()["actuals_cutoff_month_key"] is None

    def test_put_requires_biz_admin(self, serviceowner_client):
        resp = serviceowner_client.put("/api/budget/config", json={
            "fiscal_year": 2027,
            "selected_cost_elements": [],
        })
        assert resp.status_code == 403


# ══════════════════════════════════════════════════════════════════════════════
# Scenarios
# ══════════════════════════════════════════════════════════════════════════════

class TestScenarios:
    def test_create_scenario(self, bizadmin_client):
        resp = bizadmin_client.post("/api/budget/scenarios", json={
            "name": "Alt Plan",
            "fiscal_year": 2027,
            "budget_type": "NON_CONTROLLABLE",
        })
        assert resp.status_code == 201
        body = resp.json()
        assert body["name"] == "Alt Plan"
        assert body["is_baseline"] is False

    def test_create_requires_biz_admin(self, serviceowner_client):
        resp = serviceowner_client.post("/api/budget/scenarios", json={
            "name": "Alt Plan",
            "fiscal_year": 2027,
            "budget_type": "NON_CONTROLLABLE",
        })
        assert resp.status_code == 403

    def test_list_filters_by_fiscal_year(self, admin_client, db):
        make_scenario(db, fiscal_year=2027, name="FY27")
        make_scenario(db, fiscal_year=2028, name="FY28")
        resp = admin_client.get("/api/budget/scenarios?fiscal_year=2027&budget_type=NON_CONTROLLABLE")
        assert resp.status_code == 200
        names = [s["name"] for s in resp.json()]
        assert "FY27" in names
        assert "FY28" not in names

    def test_baseline_listed_first(self, admin_client, db):
        make_scenario(db, name="Alt", is_baseline=False)
        make_scenario(db, name="Baseline", is_baseline=True)
        resp = admin_client.get("/api/budget/scenarios?fiscal_year=2027&budget_type=NON_CONTROLLABLE")
        assert resp.json()[0]["is_baseline"] is True

    def test_update_scenario_name(self, bizadmin_client, db):
        s = make_scenario(db)
        resp = bizadmin_client.put(f"/api/budget/scenarios/{s.id}", json={"name": "Renamed"})
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed"

    def test_delete_non_baseline(self, bizadmin_client, db):
        s = make_scenario(db, is_baseline=False, name="Alt")
        resp = bizadmin_client.delete(f"/api/budget/scenarios/{s.id}")
        assert resp.status_code == 204

    def test_delete_baseline_rejected(self, bizadmin_client, db):
        s = make_scenario(db, is_baseline=True)
        resp = bizadmin_client.delete(f"/api/budget/scenarios/{s.id}")
        assert resp.status_code == 400

    def test_delete_nonexistent_404(self, bizadmin_client):
        resp = bizadmin_client.delete("/api/budget/scenarios/99999")
        assert resp.status_code == 404

    def test_create_copies_entries_from_source(self, bizadmin_client, db):
        src = make_scenario(db, name="Source")
        make_entry(db, src.id, department_name="Engineering",
                   entry_type="APPROVED_REC", q1=Decimal("100000"))

        resp = bizadmin_client.post("/api/budget/scenarios", json={
            "name": "Copy",
            "fiscal_year": 2027,
            "budget_type": "NON_CONTROLLABLE",
            "copy_from_scenario_id": src.id,
        })
        assert resp.status_code == 201
        new_id = resp.json()["id"]

        # Verify entries were copied into the new scenario
        plan_resp = bizadmin_client.get(
            f"/api/budget/non-controllable?fiscal_year=2027&scenario_id={new_id}"
        )
        depts = {d["department_name"]: d for d in plan_resp.json()["departments"]}
        assert float(depts["Engineering"]["approved_rec"]["q1"]) == 100000.0


# ══════════════════════════════════════════════════════════════════════════════
# Non-Controllable Plan
# ══════════════════════════════════════════════════════════════════════════════

class TestNonControllablePlan:
    def test_returns_404_for_missing_scenario(self, admin_client):
        resp = admin_client.get("/api/budget/non-controllable?fiscal_year=2027&scenario_id=99999")
        assert resp.status_code == 404

    def test_empty_plan_has_no_departments_without_spend(self, admin_client, db):
        s = make_scenario(db)
        resp = admin_client.get(f"/api/budget/non-controllable?fiscal_year=2027&scenario_id={s.id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["fiscal_year"] == 2027
        assert body["departments"] == []

    def test_plan_shows_departments_from_spend_data(self, admin_client, db):
        s = make_scenario(db)
        spend = make_spend(
            oracle_department_name="Engineering",
            oracle_cost_element="Salaries",
            month_key=202601,  # prior year (FY2027 - 1 = FY2026)
            amount_usd=Decimal("50000.00"),
        )
        db.add(spend)
        db.commit()

        # Set config to include Salaries
        admin_client.put("/api/budget/config", json={
            "fiscal_year": 2027,
            "selected_cost_elements": ["Salaries"],
            "actuals_cutoff_month_key": None,
        })

        resp = admin_client.get(f"/api/budget/non-controllable?fiscal_year=2027&scenario_id={s.id}")
        assert resp.status_code == 200
        dept_names = [d["department_name"] for d in resp.json()["departments"]]
        assert "Engineering" in dept_names

    def test_plan_includes_entry_amounts(self, admin_client, db):
        s = make_scenario(db)
        make_entry(db, s.id, department_name="Finance",
                   entry_type="APPROVED_REC", q1=Decimal("75000"), q2=Decimal("75000"))

        resp = admin_client.get(f"/api/budget/non-controllable?fiscal_year=2027&scenario_id={s.id}")
        depts = {d["department_name"]: d for d in resp.json()["departments"]}
        assert "Finance" in depts
        assert float(depts["Finance"]["approved_rec"]["q1"]) == 75000.0
        assert float(depts["Finance"]["approved_rec"]["q2"]) == 75000.0

    def test_plan_returns_entry_status_and_id(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, department_name="Sales",
                       entry_type="APPROVED_REC", status="READY_FOR_REVIEW")

        resp = admin_client.get(f"/api/budget/non-controllable?fiscal_year=2027&scenario_id={s.id}")
        depts = {d["department_name"]: d for d in resp.json()["departments"]}
        assert depts["Sales"]["approved_rec_status"] == "READY_FOR_REVIEW"
        assert depts["Sales"]["approved_rec_entry_id"] == e.id

    def test_plan_totals_sum_all_departments(self, admin_client, db):
        s = make_scenario(db)
        make_entry(db, s.id, "Engineering", "APPROVED_REC", q1=Decimal("100000"))
        make_entry(db, s.id, "Sales",       "APPROVED_REC", q1=Decimal("50000"))

        resp = admin_client.get(f"/api/budget/non-controllable?fiscal_year=2027&scenario_id={s.id}")
        totals = resp.json()["totals"]
        assert float(totals["approved_rec"]["q1"]) == 150000.0

    def test_plan_shows_available_scenarios(self, admin_client, db):
        s1 = make_scenario(db, name="Baseline", is_baseline=True)
        make_scenario(db, name="Alt", is_baseline=False)
        resp = admin_client.get(f"/api/budget/non-controllable?fiscal_year=2027&scenario_id={s1.id}")
        scenario_names = [s["name"] for s in resp.json()["scenarios"]]
        assert "Baseline" in scenario_names
        assert "Alt" in scenario_names


# ══════════════════════════════════════════════════════════════════════════════
# Entries — upsert
# ══════════════════════════════════════════════════════════════════════════════

class TestUpsertEntry:
    def _payload(self, scenario_id, **kwargs):
        base = dict(
            scenario_id=scenario_id,
            department_name="Engineering",
            entry_type="APPROVED_REC",
            q1_amount=185000,
            q2_amount=185000,
            q3_amount=190000,
            q4_amount=195000,
        )
        base.update(kwargs)
        return base

    def test_upsert_creates_new_entry(self, admin_client, db):
        s = make_scenario(db)
        resp = admin_client.put("/api/budget/entries", json=self._payload(s.id))
        assert resp.status_code == 200
        body = resp.json()
        assert body["department_name"] == "Engineering"
        assert body["status"] == "DRAFT"
        assert float(body["q1_amount"]) == 185000.0

    def test_upsert_updates_existing_entry(self, admin_client, db):
        s = make_scenario(db)
        admin_client.put("/api/budget/entries", json=self._payload(s.id))
        resp = admin_client.put("/api/budget/entries", json=self._payload(s.id, q1_amount=200000))
        assert resp.status_code == 200
        assert float(resp.json()["q1_amount"]) == 200000.0

    def test_upsert_rejects_final_entry(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="FINAL", q1=Decimal("100000"))
        resp = admin_client.put("/api/budget/entries", json=dict(
            scenario_id=s.id,
            department_name=e.department_name,
            entry_type=e.entry_type,
            q1_amount=999999,
        ))
        assert resp.status_code == 403

    def test_upsert_requires_write_role(self, readonly_client, db):
        s = make_scenario(db)
        resp = readonly_client.put("/api/budget/entries", json=self._payload(s.id))
        assert resp.status_code == 403

    def test_upsert_missing_scenario_404(self, admin_client):
        resp = admin_client.put("/api/budget/entries", json=self._payload(99999))
        assert resp.status_code == 404

    def test_upsert_creates_audit_record(self, admin_client, db):
        s = make_scenario(db)
        admin_client.put("/api/budget/entries", json=self._payload(s.id))
        audits = db.query(BudgetEntryAudit).filter_by(scenario_id=s.id).all()
        assert len(audits) == 1
        assert audits[0].event_type == "AMOUNT_CHANGED"
        assert "q1_amount" in audits[0].changes

    def test_upsert_no_audit_when_nothing_changed(self, admin_client, db):
        s = make_scenario(db)
        payload = self._payload(s.id)
        admin_client.put("/api/budget/entries", json=payload)
        admin_client.put("/api/budget/entries", json=payload)  # same values
        audits = db.query(BudgetEntryAudit).filter_by(
            scenario_id=s.id, event_type="AMOUNT_CHANGED"
        ).all()
        # Only 1 audit record (the initial create), second upsert had no diff
        assert len(audits) == 1

    def test_upsert_audit_records_only_changed_fields(self, admin_client, db):
        s = make_scenario(db)
        admin_client.put("/api/budget/entries", json=self._payload(s.id))
        admin_client.put("/api/budget/entries", json=self._payload(s.id, q1_amount=999000))
        audits = db.query(BudgetEntryAudit).filter_by(
            scenario_id=s.id, event_type="AMOUNT_CHANGED"
        ).order_by(BudgetEntryAudit.changed_at).all()
        second_audit = audits[1]
        assert "q1_amount" in second_audit.changes
        assert "q2_amount" not in second_audit.changes  # q2 didn't change


# ══════════════════════════════════════════════════════════════════════════════
# Entries — delete
# ══════════════════════════════════════════════════════════════════════════════

class TestDeleteEntry:
    def test_delete_entry(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id)
        resp = admin_client.delete(f"/api/budget/entries/{e.id}")
        assert resp.status_code == 204

    def test_delete_nonexistent_entry_404(self, admin_client):
        resp = admin_client.delete("/api/budget/entries/99999")
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Entry Status Transitions
# ══════════════════════════════════════════════════════════════════════════════

class TestEntryStatus:
    def _patch(self, client, entry_id, status):
        return client.patch(f"/api/budget/entries/{entry_id}/status", json={"status": status})

    # ── Valid transitions ─────────────────────────────────────────────────────

    def test_draft_to_ready_for_review_by_service_owner(self, serviceowner_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="DRAFT")
        resp = self._patch(serviceowner_client, e.id, "READY_FOR_REVIEW")
        assert resp.status_code == 200
        assert resp.json()["status"] == "READY_FOR_REVIEW"

    def test_draft_to_cancelled_by_service_owner(self, serviceowner_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="DRAFT")
        resp = self._patch(serviceowner_client, e.id, "CANCELLED")
        assert resp.status_code == 200

    def test_ready_for_review_to_approved_by_bizadmin(self, bizadmin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="READY_FOR_REVIEW")
        resp = self._patch(bizadmin_client, e.id, "APPROVED")
        assert resp.status_code == 200
        assert resp.json()["status"] == "APPROVED"

    def test_approved_to_final_by_bizadmin(self, bizadmin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="APPROVED")
        resp = self._patch(bizadmin_client, e.id, "FINAL")
        assert resp.status_code == 200
        assert resp.json()["status"] == "FINAL"

    def test_final_to_approved_by_admin_only(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="FINAL")
        resp = self._patch(admin_client, e.id, "APPROVED")
        assert resp.status_code == 200

    def test_cancelled_to_draft_by_admin(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="CANCELLED")
        resp = self._patch(admin_client, e.id, "DRAFT")
        assert resp.status_code == 200

    # ── Invalid transitions ───────────────────────────────────────────────────

    def test_draft_to_approved_rejected(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="DRAFT")
        resp = self._patch(admin_client, e.id, "APPROVED")
        assert resp.status_code == 400

    def test_draft_to_final_rejected(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="DRAFT")
        resp = self._patch(admin_client, e.id, "FINAL")
        assert resp.status_code == 400

    def test_final_to_draft_rejected(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="FINAL")
        resp = self._patch(admin_client, e.id, "DRAFT")
        assert resp.status_code == 400

    # ── Role enforcement ──────────────────────────────────────────────────────

    def test_service_owner_cannot_approve(self, serviceowner_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="READY_FOR_REVIEW")
        resp = self._patch(serviceowner_client, e.id, "APPROVED")
        assert resp.status_code == 403

    def test_service_owner_cannot_move_ready_to_draft(self, serviceowner_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="READY_FOR_REVIEW")
        resp = self._patch(serviceowner_client, e.id, "DRAFT")
        assert resp.status_code == 403

    def test_bizadmin_cannot_reopen_final(self, bizadmin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="FINAL")
        resp = self._patch(bizadmin_client, e.id, "APPROVED")
        assert resp.status_code == 403

    def test_readonly_cannot_change_status(self, readonly_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="DRAFT")
        resp = self._patch(readonly_client, e.id, "READY_FOR_REVIEW")
        assert resp.status_code == 403

    # ── FINAL lock ────────────────────────────────────────────────────────────

    def test_final_entry_rejects_amount_edits(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="FINAL", q1=Decimal("100000"))
        resp = admin_client.put("/api/budget/entries", json=dict(
            scenario_id=s.id,
            department_name=e.department_name,
            entry_type=e.entry_type,
            q1_amount=999999,
        ))
        assert resp.status_code == 403

    # ── Audit on status change ────────────────────────────────────────────────

    def test_status_change_creates_audit_record(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="DRAFT")
        self._patch(admin_client, e.id, "READY_FOR_REVIEW")
        audits = db.query(BudgetEntryAudit).filter_by(
            entry_id=e.id, event_type="STATUS_CHANGED"
        ).all()
        assert len(audits) == 1
        assert audits[0].changes == {"status": {"old": "DRAFT", "new": "READY_FOR_REVIEW"}}

    def test_status_change_audit_has_correct_changed_by(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="DRAFT")
        self._patch(admin_client, e.id, "READY_FOR_REVIEW")
        audit = db.query(BudgetEntryAudit).filter_by(
            entry_id=e.id, event_type="STATUS_CHANGED"
        ).first()
        assert "admin" in audit.changed_by

    def test_missing_entry_404(self, admin_client):
        resp = admin_client.patch("/api/budget/entries/99999/status", json={"status": "READY_FOR_REVIEW"})
        assert resp.status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# Scenario Audit Log
# ══════════════════════════════════════════════════════════════════════════════

class TestScenarioAudit:
    def test_audit_empty_for_new_scenario(self, admin_client, db):
        s = make_scenario(db)
        resp = admin_client.get(f"/api/budget/scenarios/{s.id}/audit")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_audit_records_amount_change(self, admin_client, db):
        s = make_scenario(db)
        admin_client.put("/api/budget/entries", json=dict(
            scenario_id=s.id,
            department_name="Engineering",
            entry_type="APPROVED_REC",
            q1_amount=100000,
        ))
        resp = admin_client.get(f"/api/budget/scenarios/{s.id}/audit")
        events = resp.json()
        assert len(events) == 1
        assert events[0]["event_type"] == "AMOUNT_CHANGED"

    def test_audit_records_status_change(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="DRAFT")
        admin_client.patch(f"/api/budget/entries/{e.id}/status", json={"status": "READY_FOR_REVIEW"})
        resp = admin_client.get(f"/api/budget/scenarios/{s.id}/audit")
        events = resp.json()
        assert any(ev["event_type"] == "STATUS_CHANGED" for ev in events)

    def test_audit_ordered_newest_first(self, admin_client, db):
        s = make_scenario(db)
        e = make_entry(db, s.id, status="DRAFT")
        admin_client.put("/api/budget/entries", json=dict(
            scenario_id=s.id,
            department_name=e.department_name,
            entry_type=e.entry_type,
            q1_amount=100000,
        ))
        admin_client.patch(f"/api/budget/entries/{e.id}/status", json={"status": "READY_FOR_REVIEW"})
        resp = admin_client.get(f"/api/budget/scenarios/{s.id}/audit")
        events = resp.json()
        # STATUS_CHANGED should be first (most recent)
        assert events[0]["event_type"] == "STATUS_CHANGED"

    def test_audit_includes_department_and_entry_type(self, admin_client, db):
        s = make_scenario(db)
        admin_client.put("/api/budget/entries", json=dict(
            scenario_id=s.id,
            department_name="Marketing",
            entry_type="ADDITIONAL_ASK",
            q1_amount=50000,
        ))
        resp = admin_client.get(f"/api/budget/scenarios/{s.id}/audit")
        event = resp.json()[0]
        assert event["department_name"] == "Marketing"
        assert event["entry_type"] == "ADDITIONAL_ASK"


# ══════════════════════════════════════════════════════════════════════════════
# Scenario Comparison
# ══════════════════════════════════════════════════════════════════════════════

class TestScenarioComparison:
    def test_compare_missing_scenario_404(self, admin_client, db):
        s = make_scenario(db)
        resp = admin_client.get(f"/api/budget/compare?fiscal_year=2027&scenario_a_id={s.id}&scenario_b_id=99999")
        assert resp.status_code == 404

    def test_compare_identical_scenarios_zero_delta(self, admin_client, db):
        s1 = make_scenario(db, name="Baseline", is_baseline=True)
        s2 = make_scenario(db, name="Alt", is_baseline=False)
        for sid in (s1.id, s2.id):
            make_entry(db, sid, "Engineering", "APPROVED_REC",
                       q1=Decimal("100000"), q2=Decimal("100000"))

        resp = admin_client.get(
            f"/api/budget/compare?fiscal_year=2027&scenario_a_id={s1.id}&scenario_b_id={s2.id}"
        )
        assert resp.status_code == 200
        totals = resp.json()["totals"]
        assert float(totals["approved_rec_delta"]["annual"]) == 0.0
        assert totals["approved_rec_delta"]["annual_pct"] == 0.0

    def test_compare_returns_positive_delta(self, admin_client, db):
        s1 = make_scenario(db, name="Baseline", is_baseline=True)
        s2 = make_scenario(db, name="Higher", is_baseline=False)
        make_entry(db, s1.id, "Engineering", "APPROVED_REC", q1=Decimal("100000"))
        make_entry(db, s2.id, "Engineering", "APPROVED_REC", q1=Decimal("120000"))

        resp = admin_client.get(
            f"/api/budget/compare?fiscal_year=2027&scenario_a_id={s1.id}&scenario_b_id={s2.id}"
        )
        assert resp.status_code == 200
        delta = resp.json()["totals"]["approved_rec_delta"]
        assert float(delta["q1"]) == 20000.0
        assert float(delta["q1_pct"]) == 20.0

    def test_compare_shows_both_scenarios_in_all_scenarios(self, admin_client, db):
        s1 = make_scenario(db, name="A", is_baseline=True)
        s2 = make_scenario(db, name="B", is_baseline=False)
        resp = admin_client.get(
            f"/api/budget/compare?fiscal_year=2027&scenario_a_id={s1.id}&scenario_b_id={s2.id}"
        )
        all_names = [s["name"] for s in resp.json()["all_scenarios"]]
        assert "A" in all_names
        assert "B" in all_names

    def test_compare_dept_with_entry_in_only_one_scenario(self, admin_client, db):
        s1 = make_scenario(db, name="Baseline", is_baseline=True)
        s2 = make_scenario(db, name="Alt", is_baseline=False)
        make_entry(db, s1.id, "Finance", "APPROVED_REC", q1=Decimal("50000"))
        # s2 has no entry for Finance

        resp = admin_client.get(
            f"/api/budget/compare?fiscal_year=2027&scenario_a_id={s1.id}&scenario_b_id={s2.id}"
        )
        depts = {d["department_name"]: d for d in resp.json()["departments"]}
        finance = depts["Finance"]
        assert float(finance["approved_rec_a"]["q1"]) == 50000.0
        assert float(finance["approved_rec_b"]["q1"]) == 0.0
        assert float(finance["approved_rec_delta"]["q1"]) == -50000.0


# ══════════════════════════════════════════════════════════════════════════════
# Cost Elements
# ══════════════════════════════════════════════════════════════════════════════

class TestCostElements:
    def test_returns_empty_list_when_no_spend(self, admin_client):
        resp = admin_client.get("/api/budget/cost-elements")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_distinct_elements(self, admin_client, db):
        for cost_element in ("Salaries", "Travel", "Salaries"):
            spend = make_spend(oracle_cost_element=cost_element)
            db.add(spend)
        db.commit()

        resp = admin_client.get("/api/budget/cost-elements")
        elements = resp.json()
        assert elements == sorted(set(elements))
        assert elements.count("Salaries") == 1


# ══════════════════════════════════════════════════════════════════════════════
# Budget Scenario Audit
# ══════════════════════════════════════════════════════════════════════════════

class TestBudgetScenarioAudit:
    def _scenario_payload(self, **overrides):
        base = dict(name="Test Scenario", fiscal_year=2027, budget_type="NON_CONTROLLABLE")
        base.update(overrides)
        return base

    def test_create_scenario_logged(self, bizadmin_client):
        r = bizadmin_client.post("/api/budget/scenarios", json=self._scenario_payload())
        assert r.status_code == 201
        scenario_id = r.json()["id"]

        audit = bizadmin_client.get(f"/api/budget/scenario-audit?scenario_id={scenario_id}").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "CREATED"
        assert audit[0]["changes"] == {}
        assert audit[0]["scenario_name"] == "Test Scenario"

    def test_update_scenario_logged(self, bizadmin_client, db):
        s = make_scenario(db, name="Old Name")
        bizadmin_client.put(f"/api/budget/scenarios/{s.id}", json={"name": "New Name"})

        audit = bizadmin_client.get(f"/api/budget/scenario-audit?scenario_id={s.id}").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "UPDATED"
        assert audit[0]["changes"]["name"]["old"] == "Old Name"
        assert audit[0]["changes"]["name"]["new"] == "New Name"

    def test_update_no_change_no_audit(self, bizadmin_client, db):
        s = make_scenario(db, name="Same")
        bizadmin_client.put(f"/api/budget/scenarios/{s.id}", json={"name": "Same"})
        audit = bizadmin_client.get(f"/api/budget/scenario-audit?scenario_id={s.id}").json()
        assert len(audit) == 0

    def test_delete_scenario_logged(self, bizadmin_client, db):
        s = make_scenario(db, name="To Delete", is_baseline=False)
        scenario_id = s.id
        r = bizadmin_client.delete(f"/api/budget/scenarios/{scenario_id}")
        assert r.status_code == 204

        audit = bizadmin_client.get(f"/api/budget/scenario-audit?scenario_id={scenario_id}").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "DELETED"

    def test_filter_by_fiscal_year(self, bizadmin_client):
        bizadmin_client.post("/api/budget/scenarios", json=self._scenario_payload(fiscal_year=2027, name="S1"))
        bizadmin_client.post("/api/budget/scenarios", json=self._scenario_payload(fiscal_year=2028, name="S2"))

        audit = bizadmin_client.get("/api/budget/scenario-audit?fiscal_year=2027").json()
        assert all(a["fiscal_year"] == 2027 for a in audit)

    def test_audit_requires_auth(self, client):
        r = client.get("/api/budget/scenario-audit")
        assert r.status_code == 401

    def test_readonly_can_view_audit(self, readonly_client, bizadmin_client):
        bizadmin_client.post("/api/budget/scenarios", json=self._scenario_payload())
        r = readonly_client.get("/api/budget/scenario-audit?fiscal_year=2027")
        assert r.status_code == 200


# ══════════════════════════════════════════════════════════════════════════════
# Budget NC Config Audit
# ══════════════════════════════════════════════════════════════════════════════

class TestBudgetNcConfigAudit:
    def test_create_config_logged(self, bizadmin_client):
        r = bizadmin_client.put("/api/budget/config", json={
            "fiscal_year": 2027,
            "selected_cost_elements": ["Salaries"],
            "actuals_cutoff_month_key": None,
        })
        assert r.status_code == 200

        audit = bizadmin_client.get("/api/budget/config/audit?fiscal_year=2027").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "CREATED"
        assert audit[0]["changes"] == {}

    def test_update_config_logged(self, bizadmin_client):
        bizadmin_client.put("/api/budget/config", json={
            "fiscal_year": 2027, "selected_cost_elements": [], "actuals_cutoff_month_key": None,
        })
        bizadmin_client.put("/api/budget/config", json={
            "fiscal_year": 2027, "selected_cost_elements": ["Travel"], "actuals_cutoff_month_key": 202606,
        })

        audit = bizadmin_client.get("/api/budget/config/audit?fiscal_year=2027").json()
        assert len(audit) == 2
        update = next(a for a in audit if a["event_type"] == "UPDATED")
        assert update["changes"]["selected_cost_elements"]["old"] == []
        assert update["changes"]["selected_cost_elements"]["new"] == ["Travel"]
        assert update["changes"]["actuals_cutoff_month_key"]["new"] == 202606

    def test_update_no_change_no_audit(self, bizadmin_client):
        payload = {"fiscal_year": 2027, "selected_cost_elements": ["Salaries"], "actuals_cutoff_month_key": None}
        bizadmin_client.put("/api/budget/config", json=payload)  # CREATED
        bizadmin_client.put("/api/budget/config", json=payload)  # same values — no UPDATED row

        audit = bizadmin_client.get("/api/budget/config/audit?fiscal_year=2027").json()
        assert len(audit) == 1
        assert audit[0]["event_type"] == "CREATED"

    def test_audit_requires_auth(self, client):
        r = client.get("/api/budget/config/audit")
        assert r.status_code == 401

    def test_readonly_can_view_audit(self, readonly_client, bizadmin_client):
        bizadmin_client.put("/api/budget/config", json={
            "fiscal_year": 2027, "selected_cost_elements": [], "actuals_cutoff_month_key": None,
        })
        r = readonly_client.get("/api/budget/config/audit?fiscal_year=2027")
        assert r.status_code == 200
        assert len(r.json()) == 1
