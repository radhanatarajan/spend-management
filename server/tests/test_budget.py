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
from datetime import date
from decimal import Decimal

import pytest

from src.models.budget import BudgetEntryAudit, ControllableBudgetEntry, ControllableLineOverride
from src.models.user import UserRole
from tests.conftest import make_scenario, make_entry, make_spend, make_contract


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


class TestAccountGroups:
    def test_returns_empty_list_when_no_spend(self, admin_client):
        resp = admin_client.get("/api/budget/account-groups")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_distinct_groups(self, admin_client, db):
        for group in ("R&D", "G&A", "R&D"):
            db.add(make_spend(oracle_account_group=group))
        db.commit()

        resp = admin_client.get("/api/budget/account-groups")
        groups = resp.json()
        assert groups == sorted(set(groups))
        assert groups.count("R&D") == 1

    def test_requires_auth(self, client):
        assert client.get("/api/budget/account-groups").status_code == 401


class TestAccountSubGroups:
    def test_returns_empty_list_when_no_spend(self, admin_client):
        resp = admin_client.get("/api/budget/account-sub-groups")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_returns_distinct_sub_groups(self, admin_client, db):
        for sub in ("Cloud Infra", "Salaries", "Cloud Infra"):
            db.add(make_spend(oracle_account_sub_group=sub))
        db.commit()

        resp = admin_client.get("/api/budget/account-sub-groups")
        sub_groups = resp.json()
        assert sub_groups == sorted(set(sub_groups))
        assert sub_groups.count("Cloud Infra") == 1

    def test_requires_auth(self, client):
        assert client.get("/api/budget/account-sub-groups").status_code == 401


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


# ══════════════════════════════════════════════════════════════════════════════
# Controllable Budget
# ══════════════════════════════════════════════════════════════════════════════

def make_controllable_entry(db, scenario_id, activity_id=None, entry_label=None,
                             entry_category="EXISTING", q1=None, q2=None, q3=None, q4=None,
                             status="DRAFT"):
    e = ControllableBudgetEntry(
        scenario_id=scenario_id,
        fiscal_year=2027,
        activity_id=activity_id,
        entry_label=entry_label,
        entry_category=entry_category,
        q1_amount=q1,
        q2_amount=q2,
        q3_amount=q3,
        q4_amount=q4,
        status=status,
        created_by="admin@test.com",
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return e


def make_line_override(db, scenario_id, contract_line_id, action="keep",
                       q1_extended=None, q2_extended=None, q3_extended=None, q4_extended=None):
    o = ControllableLineOverride(
        scenario_id=scenario_id,
        contract_line_id=contract_line_id,
        action=action,
        q1_extended=q1_extended,
        q2_extended=q2_extended,
        q3_extended=q3_extended,
        q4_extended=q4_extended,
        created_by="admin@test.com",
    )
    db.add(o)
    db.commit()
    db.refresh(o)
    return o


class TestControllableBudget:
    FY = 2027

    def _ctrl_scenario(self, db, name="C-Baseline"):
        return make_scenario(db, fiscal_year=self.FY, name=name, budget_type="CONTROLLABLE")

    def _contract_with_activity(self, db, activity_id="ACT-001", monthly=1000, vendor="Vendor A"):
        return make_contract(db, vendor=vendor, po=f"PO-{activity_id}", lines=[{
            "po_line_number": 1,
            "activity_id": activity_id,
            "period_start": date(self.FY, 1, 1),
            "period_end": date(self.FY, 12, 31),
            "billing_interval": "monthly",
            "entered_amount": Decimal(str(monthly)),
        }])

    # ── Plan endpoint ──────────────────────────────────────────────────────────

    def test_plan_returns_rows_for_activity_ids_in_contracts(self, admin_client, db):
        scenario = self._ctrl_scenario(db)
        self._contract_with_activity(db, activity_id="ACT-001", monthly=5000)

        r = admin_client.get(f"/api/budget/controllable?fiscal_year={self.FY}&scenario_id={scenario.id}")
        assert r.status_code == 200
        data = r.json()
        assert data["fiscal_year"] == self.FY
        rows = data["rows"]
        assert len(rows) == 1
        assert rows[0]["activity_id"] == "ACT-001"
        # 12 months × $5000/mo = $60,000
        assert float(rows[0]["current_and_forecast"]) == pytest.approx(60000.0)

    def test_plan_excludes_unassigned_lines(self, admin_client, db):
        scenario = self._ctrl_scenario(db)
        # Contract line with no activity_id
        make_contract(db, vendor="No-Act", po="PO-NACT", lines=[{
            "po_line_number": 1,
            "activity_id": None,
            "period_start": date(self.FY, 1, 1),
            "period_end": date(self.FY, 12, 31),
            "billing_interval": "monthly",
            "entered_amount": Decimal("3000"),
        }])
        r = admin_client.get(f"/api/budget/controllable?fiscal_year={self.FY}&scenario_id={scenario.id}")
        assert r.status_code == 200
        assert r.json()["rows"] == []

    def test_plan_shows_new_request_entries(self, admin_client, db):
        scenario = self._ctrl_scenario(db)
        make_controllable_entry(db, scenario.id, entry_label="New SaaS Vendor",
                                entry_category="NEW_REQUEST", q1=Decimal("10000"))

        r = admin_client.get(f"/api/budget/controllable?fiscal_year={self.FY}&scenario_id={scenario.id}")
        assert r.status_code == 200
        rows = r.json()["rows"]
        new_rows = [ro for ro in rows if ro["entry_category"] == "NEW_REQUEST"]
        assert len(new_rows) == 1
        assert new_rows[0]["entry_label"] == "New SaaS Vendor"
        assert float(new_rows[0]["current_and_forecast"]) == 0.0

    def test_plan_syncs_contracted_amounts_to_entry(self, admin_client, db):
        # For EXISTING rows, the plan endpoint auto-syncs contracted quarterly
        # amounts into budget_entries. Pre-existing manual amounts are overwritten
        # because q1-q4 in entries always mirror the contracted totals.
        scenario = self._ctrl_scenario(db)
        self._contract_with_activity(db, activity_id="ACT-002", monthly=2000)
        # 2000/mo × 12 months → Q1=Q2=Q3=Q4 = 3 mo × 2000 = 6000 each, total 24000

        r = admin_client.get(f"/api/budget/controllable?fiscal_year={self.FY}&scenario_id={scenario.id}")
        assert r.status_code == 200
        row = r.json()["rows"][0]
        assert row["activity_id"] == "ACT-002"
        # contracted quarterly totals auto-persisted to entry
        assert float(row["q1_amount"]) == pytest.approx(6000.0)
        assert float(row["total_budget"]) == pytest.approx(24000.0)
        assert row["entry_id"] is not None  # entry auto-created
        assert row["status"] == "DRAFT"

    def test_plan_wrong_scenario_type_returns_404(self, admin_client, db):
        nc_scenario = make_scenario(db, fiscal_year=self.FY, budget_type="NON_CONTROLLABLE")
        r = admin_client.get(f"/api/budget/controllable?fiscal_year={self.FY}&scenario_id={nc_scenario.id}")
        assert r.status_code == 404

    # ── Line overrides ─────────────────────────────────────────────────────────

    def test_cancel_override_zeroes_contribution(self, admin_client, bizadmin_client, db):
        scenario = self._ctrl_scenario(db)
        contract = self._contract_with_activity(db, activity_id="ACT-003", monthly=1000)
        line_id = contract.lines[0].id

        bizadmin_client.put("/api/budget/controllable/line-overrides", json={
            "scenario_id": scenario.id,
            "contract_line_id": line_id,
            "action": "cancel",
        })

        r = admin_client.get(f"/api/budget/controllable?fiscal_year={self.FY}&scenario_id={scenario.id}")
        row = r.json()["rows"][0]
        # C+F is raw contracted total; cancel only zeroes the plan columns, not C+F
        assert float(row["current_and_forecast"]) == pytest.approx(12000.0)
        assert row["lines"][0]["override_action"] == "cancel"

    def test_extend_override_applies_new_amount(self, admin_client, bizadmin_client, db):
        scenario = self._ctrl_scenario(db)
        contract = self._contract_with_activity(db, activity_id="ACT-004", monthly=1000)
        line_id = contract.lines[0].id

        # Override with quarterly extended amounts (Q1-Q4 of FY2027)
        bizadmin_client.put("/api/budget/controllable/line-overrides", json={
            "scenario_id": scenario.id,
            "contract_line_id": line_id,
            "action": "extend",
            "q1_extended": 6000,
            "q2_extended": 6000,
            "q3_extended": 6000,
            "q4_extended": 6000,
        })

        r = admin_client.get(f"/api/budget/controllable?fiscal_year={self.FY}&scenario_id={scenario.id}")
        row = r.json()["rows"][0]
        # C+F is raw contracted total; extend only affects plan columns, not C+F
        assert float(row["current_and_forecast"]) == pytest.approx(12000.0)
        # Plan columns reflect the extended amounts (Q1+Q2+Q3+Q4 = $24,000)
        assert float(row["q1_contracted"]) + float(row["q2_contracted"]) + float(row["q3_contracted"]) + float(row["q4_contracted"]) == pytest.approx(24000.0)

    def test_extend_accepts_partial_quarters(self, bizadmin_client, db):
        # Extend with only some quarters set is valid (others default to 0)
        scenario = self._ctrl_scenario(db)
        contract = self._contract_with_activity(db, activity_id="ACT-005", monthly=1000)
        line_id = contract.lines[0].id
        r = bizadmin_client.put("/api/budget/controllable/line-overrides", json={
            "scenario_id": scenario.id,
            "contract_line_id": line_id,
            "action": "extend",
            "q1_extended": 5000,
        })
        assert r.status_code == 200

    def test_line_override_writes_audit_row(self, bizadmin_client, db):
        from src.models.budget import ControllableBudgetAudit
        scenario = self._ctrl_scenario(db)
        contract = self._contract_with_activity(db, activity_id="ACT-AUD", monthly=1000)
        line_id = contract.lines[0].id
        r = bizadmin_client.put("/api/budget/controllable/line-overrides", json={
            "scenario_id": scenario.id,
            "contract_line_id": line_id,
            "action": "extend",
            "q4_extended": 9999,
        })
        assert r.status_code == 200
        audit_rows = db.query(ControllableBudgetAudit).filter(
            ControllableBudgetAudit.scenario_id == scenario.id,
            ControllableBudgetAudit.event_type == "AMOUNT_CHANGED",
        ).all()
        assert len(audit_rows) == 1
        changes = audit_rows[0].changes
        assert "q4_amount" in changes
        assert changes["q4_amount"]["new"] == "9999.00"

    def test_readonly_cannot_set_override(self, readonly_client, db):
        scenario = self._ctrl_scenario(db)
        contract = self._contract_with_activity(db, activity_id="ACT-006", monthly=500)
        r = readonly_client.put("/api/budget/controllable/line-overrides", json={
            "scenario_id": scenario.id,
            "contract_line_id": contract.lines[0].id,
            "action": "cancel",
        })
        assert r.status_code == 403

    # ── Entry upsert ───────────────────────────────────────────────────────────

    def test_upsert_creates_entry(self, bizadmin_client, db):
        scenario = self._ctrl_scenario(db)
        self._contract_with_activity(db, activity_id="ACT-007", monthly=500)

        r = bizadmin_client.put("/api/budget/controllable/entries", json={
            "scenario_id": scenario.id,
            "fiscal_year": self.FY,
            "activity_id": "ACT-007",
            "entry_category": "EXISTING",
            "q1_amount": 15000,
            "q2_amount": 15000,
            "q3_amount": 15000,
            "q4_amount": 15000,
        })
        assert r.status_code == 200
        data = r.json()
        assert data["activity_id"] == "ACT-007"
        assert float(data["q1_amount"]) == pytest.approx(15000.0)

    def test_upsert_updates_existing_entry(self, bizadmin_client, db):
        scenario = self._ctrl_scenario(db)
        self._contract_with_activity(db, activity_id="ACT-008", monthly=500)
        bizadmin_client.put("/api/budget/controllable/entries", json={
            "scenario_id": scenario.id, "fiscal_year": self.FY,
            "activity_id": "ACT-008", "entry_category": "EXISTING",
            "q1_amount": 1000,
        })
        r = bizadmin_client.put("/api/budget/controllable/entries", json={
            "scenario_id": scenario.id, "fiscal_year": self.FY,
            "activity_id": "ACT-008", "entry_category": "EXISTING",
            "q1_amount": 9999,
        })
        assert r.status_code == 200
        assert float(r.json()["q1_amount"]) == pytest.approx(9999.0)

    def test_readonly_cannot_upsert(self, readonly_client, db):
        scenario = self._ctrl_scenario(db)
        r = readonly_client.put("/api/budget/controllable/entries", json={
            "scenario_id": scenario.id, "fiscal_year": self.FY,
            "entry_category": "NEW_REQUEST", "entry_label": "Test",
        })
        assert r.status_code == 403

    # ── Status transitions ─────────────────────────────────────────────────────

    def test_status_transition_draft_to_ready(self, bizadmin_client, db):
        scenario = self._ctrl_scenario(db)
        entry = make_controllable_entry(db, scenario.id, activity_id="ACT-009")
        r = bizadmin_client.patch(f"/api/budget/controllable/entries/{entry.id}/status",
                                  json={"status": "READY_FOR_REVIEW"})
        assert r.status_code == 200
        assert r.json()["status"] == "READY_FOR_REVIEW"

    def test_status_transition_invalid_role_forbidden(self, serviceowner_client, db):
        scenario = self._ctrl_scenario(db)
        entry = make_controllable_entry(db, scenario.id, activity_id="ACT-010",
                                        status="READY_FOR_REVIEW")
        # SERVICE_OWNER cannot approve
        r = serviceowner_client.patch(f"/api/budget/controllable/entries/{entry.id}/status",
                                      json={"status": "APPROVED"})
        assert r.status_code == 403

    def test_status_transition_invalid_transition_forbidden(self, bizadmin_client, db):
        scenario = self._ctrl_scenario(db)
        entry = make_controllable_entry(db, scenario.id, activity_id="ACT-011", status="DRAFT")
        # Cannot go directly DRAFT → FINAL
        r = bizadmin_client.patch(f"/api/budget/controllable/entries/{entry.id}/status",
                                  json={"status": "FINAL"})
        assert r.status_code == 403

    def test_readonly_cannot_transition(self, readonly_client, db):
        scenario = self._ctrl_scenario(db)
        entry = make_controllable_entry(db, scenario.id, activity_id="ACT-012")
        r = readonly_client.patch(f"/api/budget/controllable/entries/{entry.id}/status",
                                  json={"status": "READY_FOR_REVIEW"})
        assert r.status_code == 403

    def test_expense_type_stored_and_returned(self, bizadmin_client, db):
        scenario = self._ctrl_scenario(db)
        r = bizadmin_client.put("/api/budget/controllable/entries", json={
            "scenario_id": scenario.id,
            "fiscal_year": self.FY,
            "entry_category": "NEW_REQUEST",
            "entry_label": "Capex Tool",
            "expense_type": "capex",
            "q1_amount": 5000,
        })
        assert r.status_code == 200
        assert r.json()["expense_type"] == "capex"

    def test_upsert_by_entry_id_links_activity_id(self, bizadmin_client, admin_client, db):
        # Simulate the post-FINAL "Create Activity ID" flow: upsert using entry_id
        # to assign an activity_id to a NEW_REQUEST entry that is FINAL.
        scenario = self._ctrl_scenario(db)
        entry = make_controllable_entry(
            db, scenario.id,
            entry_category="NEW_REQUEST", entry_label="Acme Software",
            q1=Decimal("10000"), status="FINAL",
        )
        r = bizadmin_client.put("/api/budget/controllable/entries", json={
            "entry_id": entry.id,
            "scenario_id": scenario.id,
            "fiscal_year": self.FY,
            "activity_id": "AOPEX-9999999",
            "entry_label": entry.entry_label,
            "entry_category": "NEW_REQUEST",
            "q1_amount": 10000,
        })
        assert r.status_code == 200
        assert r.json()["activity_id"] == "AOPEX-9999999"

    def test_activity_id_assignment_writes_audit_row(self, bizadmin_client, db):
        # When an activity_id is assigned to a FINAL NEW_REQUEST entry via entry_id upsert,
        # an UPDATED audit row must be written capturing the activity_id change.
        from src.models.budget import ControllableBudgetAudit
        scenario = self._ctrl_scenario(db)
        entry = make_controllable_entry(
            db, scenario.id,
            entry_category="NEW_REQUEST", entry_label="Audit Test",
            q1=Decimal("7000"), status="FINAL",
        )
        r = bizadmin_client.put("/api/budget/controllable/entries", json={
            "entry_id": entry.id,
            "scenario_id": scenario.id,
            "fiscal_year": self.FY,
            "activity_id": "AOPEX-1234567",
            "entry_label": entry.entry_label,
            "entry_category": "NEW_REQUEST",
            "q1_amount": 7000,
        })
        assert r.status_code == 200
        audit_rows = db.query(ControllableBudgetAudit).filter(
            ControllableBudgetAudit.entry_id == entry.id,
            ControllableBudgetAudit.event_type == "UPDATED",
        ).all()
        assert len(audit_rows) == 1
        changes = audit_rows[0].changes
        assert "activity_id" in changes
        assert changes["activity_id"]["old"] is None
        assert changes["activity_id"]["new"] == "AOPEX-1234567"

    def test_plan_returns_activity_id_on_new_request_after_assignment(self, admin_client, db):
        # Once an activity_id is assigned to a NEW_REQUEST entry it must appear
        # in the plan row so the UI can display it.
        scenario = self._ctrl_scenario(db)
        make_controllable_entry(
            db, scenario.id,
            activity_id="AOPEX-8888888",
            entry_category="NEW_REQUEST", entry_label="Linked Request",
            q1=Decimal("5000"),
        )
        r = admin_client.get(f"/api/budget/controllable?fiscal_year={self.FY}&scenario_id={scenario.id}")
        assert r.status_code == 200
        new_rows = [ro for ro in r.json()["rows"] if ro["entry_category"] == "NEW_REQUEST"]
        assert len(new_rows) == 1
        assert new_rows[0]["activity_id"] == "AOPEX-8888888"

    # ── Controllable comparison ────────────────────────────────────────────────

    def test_compare_returns_delta_between_two_scenarios(self, admin_client, db):
        sc_a = self._ctrl_scenario(db, name="Ctrl-A")
        sc_b = self._ctrl_scenario(db, name="Ctrl-B")
        make_controllable_entry(db, sc_a.id, activity_id="CMP-001", entry_category="EXISTING",
                                q1=Decimal("10000"), q2=Decimal("10000"))
        make_controllable_entry(db, sc_b.id, activity_id="CMP-001", entry_category="EXISTING",
                                q1=Decimal("12000"), q2=Decimal("10000"))

        r = admin_client.get(
            f"/api/budget/controllable/compare"
            f"?fiscal_year={self.FY}&scenario_a_id={sc_a.id}&scenario_b_id={sc_b.id}"
        )
        assert r.status_code == 200
        data = r.json()
        assert data["scenario_a"]["name"] == "Ctrl-A"
        assert data["scenario_b"]["name"] == "Ctrl-B"
        assert len(data["departments"]) >= 1
        # Find the row for CMP-001
        rows = [row for dept in data["departments"] for row in dept["rows"] if row["activity_id"] == "CMP-001"]
        assert len(rows) == 1
        row = rows[0]
        assert float(row["budget_a"]["q1"]) == pytest.approx(10000.0)
        assert float(row["budget_b"]["q1"]) == pytest.approx(12000.0)
        assert float(row["budget_delta"]["q1"]) == pytest.approx(2000.0)
        assert float(row["budget_delta"]["q2"]) == pytest.approx(0.0)
        # Annual totals
        assert float(data["totals_a"]["annual"]) == pytest.approx(20000.0)
        assert float(data["totals_b"]["annual"]) == pytest.approx(22000.0)
        assert float(data["totals_delta"]["annual"]) == pytest.approx(2000.0)

    def test_compare_entry_only_in_one_scenario_shows_zero_other_side(self, admin_client, db):
        sc_a = self._ctrl_scenario(db, name="Ctrl-C")
        sc_b = self._ctrl_scenario(db, name="Ctrl-D")
        # Entry only in A
        make_controllable_entry(db, sc_a.id, activity_id="CMP-002", entry_category="EXISTING",
                                q1=Decimal("5000"))
        # Different entry only in B
        make_controllable_entry(db, sc_b.id, entry_label="Extra Request", entry_category="NEW_REQUEST",
                                q4=Decimal("3000"))

        r = admin_client.get(
            f"/api/budget/controllable/compare"
            f"?fiscal_year={self.FY}&scenario_a_id={sc_a.id}&scenario_b_id={sc_b.id}"
        )
        assert r.status_code == 200
        data = r.json()
        all_rows = [row for dept in data["departments"] for row in dept["rows"]]
        cmp002 = next(row for row in all_rows if row["activity_id"] == "CMP-002")
        assert float(cmp002["budget_a"]["q1"]) == pytest.approx(5000.0)
        assert float(cmp002["budget_b"]["q1"]) == pytest.approx(0.0)
        extra = next(row for row in all_rows if row["entry_label"] == "Extra Request")
        assert float(extra["budget_a"]["q4"]) == pytest.approx(0.0)
        assert float(extra["budget_b"]["q4"]) == pytest.approx(3000.0)

    def test_compare_wrong_budget_type_returns_404(self, admin_client, db):
        ctrl = self._ctrl_scenario(db, name="Ctrl-E")
        nc = make_scenario(db, fiscal_year=self.FY, budget_type="NON_CONTROLLABLE")
        r = admin_client.get(
            f"/api/budget/controllable/compare"
            f"?fiscal_year={self.FY}&scenario_a_id={ctrl.id}&scenario_b_id={nc.id}"
        )
        assert r.status_code == 404
