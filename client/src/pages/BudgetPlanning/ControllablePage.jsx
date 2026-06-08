import { useState, useMemo } from "react";
import axios from "axios";
import { useScenarios, useControllablePlan, useUpsertControllableEntry } from "../../data/budget/hooks";
import { useAccounts } from "../../data/reference/hooks";
import ScenarioPanel from "./components/ScenarioPanel";
import ActualsCutoffControl from "./components/ActualsCutoffControl";
import ControllableTable from "./components/ControllableTable";
import DropdownSlicer from "../../components/DropdownSlicer";

const fmtCompact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
const fmtK = (v) => fmtCompact.format(Number(v ?? 0));
const fmtFull = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });

function KpiCell({ label, value, accent }) {
  return (
    <div className="flex-1 px-4 py-2 text-center min-w-[100px]">
      <div className="text-[9px] text-gray-400 uppercase tracking-wide mb-0.5">{label}</div>
      <div className={`text-sm font-bold tabular-nums ${accent || "text-gray-900"}`}>{value}</div>
    </div>
  );
}

const CURRENT_YEAR = new Date().getFullYear();

function NewRequestModal({ onClose, onSubmit, loading, filterOptions }) {
  const [form, setForm] = useState({
    label: "", department: "", costElement: "",
    accountGroup: "", accountSubGroup: "",
    expenseType: "opex",
    q1: "", q2: "", q3: "", q4: "",
  });
  const set = (field) => (e) => setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const inputCls = "w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300";
  const labelCls = "block text-xs text-gray-500 mb-1";

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-lg overflow-y-auto max-h-[90vh]">
        <h3 className="text-sm font-semibold text-gray-900 mb-4">New Controllable Request</h3>

        <div className="space-y-3">
          {/* Description */}
          <div>
            <label className={labelCls}>Description / Label <span className="text-red-400">*</span></label>
            <input autoFocus type="text" value={form.label} onChange={set("label")}
              placeholder="e.g. New SaaS vendor — Acme Software" className={inputCls} />
          </div>

          {/* Department + Cost Element */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Department</label>
              <select value={form.department} onChange={set("department")} className={inputCls}>
                <option value="">— Select —</option>
                {filterOptions.depts.map((d) => <option key={d} value={d}>{d}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Cost Element</label>
              <select value={form.costElement} onChange={set("costElement")} className={inputCls}>
                <option value="">— Select —</option>
                {filterOptions.costElements.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
          </div>

          {/* Expense Type */}
          <div>
            <label className={labelCls}>Expense Type</label>
            <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
              {[["opex","Opex"],["capex","Capex"]].map(([t, lbl]) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => setForm((prev) => ({ ...prev, expenseType: t }))}
                  className={`flex-1 py-1.5 font-medium transition-colors ${
                    form.expenseType === t
                      ? "bg-indigo-600 text-white"
                      : "bg-white text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  {lbl}
                </button>
              ))}
            </div>
          </div>

          {/* Account Group + Sub Group */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className={labelCls}>Account Group</label>
              <select value={form.accountGroup} onChange={set("accountGroup")} className={inputCls}>
                <option value="">— Select —</option>
                {filterOptions.accountGroups.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <label className={labelCls}>Account Sub Group</label>
              <select value={form.accountSubGroup} onChange={set("accountSubGroup")} className={inputCls}>
                <option value="">— Select —</option>
                {filterOptions.accountSubGroups.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </div>

          {/* Q1–Q4 amounts */}
          <div>
            <label className={labelCls}>Budget Amounts</label>
            <div className="grid grid-cols-4 gap-2">
              {[["q1","Q1 (Jan–Mar)"],["q2","Q2 (Apr–Jun)"],["q3","Q3 (Jul–Sep)"],["q4","Q4 (Oct–Dec)"]].map(([q, lbl]) => (
                <div key={q}>
                  <div className="text-[10px] text-gray-400 mb-0.5">{lbl}</div>
                  <input type="number" value={form[q]} onChange={set(q)} placeholder="0"
                    className="w-full border border-gray-200 rounded-lg px-2 py-1.5 text-sm text-right focus:outline-none focus:ring-2 focus:ring-indigo-300" />
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-2 mt-5">
          <button onClick={onClose} className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700">Cancel</button>
          <button
            disabled={!form.label.trim() || loading}
            onClick={() => onSubmit(form)}
            className="px-4 py-1.5 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
          >
            Add Request
          </button>
        </div>
      </div>
    </div>
  );
}

function CreateActivityIdModal({ row, onClose, onSuccess }) {
  const { data: allAccounts = [] } = useAccounts();

  const [expenseType, setExpenseType] = useState("opex");
  const [desc, setDesc]               = useState(row.entry_label ?? "");
  const [ceFilter, setCeFilter]       = useState(row.cost_element ?? "");
  const [agFilter, setAgFilter]       = useState(row.account_group ?? "");
  const [asgFilter, setAsgFilter]     = useState(row.account_sub_group ?? "");
  const [selectedAcct, setSelectedAcct] = useState(null);
  const [saving, setSaving]           = useState(false);
  const [err, setErr]                 = useState("");
  const [createdId, setCreatedId]     = useState(null);

  const prefix = expenseType === "capex" ? "ACAPEX" : "AOPEX";

  const costElements  = [...new Set(allAccounts.map((a) => a.cost_element).filter(Boolean))].sort();
  const accountGroups = [...new Set(
    allAccounts.filter((a) => !ceFilter || a.cost_element === ceFilter)
               .map((a) => a.account_group).filter(Boolean)
  )].sort();
  const subGroups = [...new Set(
    allAccounts.filter((a) =>
      (!ceFilter || a.cost_element === ceFilter) &&
      (!agFilter || a.account_group === agFilter)
    ).map((a) => a.account_sub_group).filter(Boolean)
  )].sort();
  const filteredAccounts = allAccounts.filter((a) =>
    (!ceFilter  || a.cost_element      === ceFilter) &&
    (!agFilter  || a.account_group     === agFilter) &&
    (!asgFilter || a.account_sub_group === asgFilter)
  );

  const selectCls = "w-full border border-gray-200 rounded-lg px-2 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-indigo-300 bg-white";
  const labelCls  = "block text-[10px] text-gray-400 uppercase tracking-wide mb-0.5";
  const rowCls = (id) =>
    `grid grid-cols-[1fr_1.5fr_1fr_1fr] gap-2 items-center px-2 py-1.5 cursor-pointer text-xs transition-colors ${
      selectedAcct?.id === id
        ? "bg-indigo-50 text-indigo-700 font-medium"
        : "hover:bg-gray-50 text-gray-600"
    }`;

  async function handleCreate() {
    setSaving(true); setErr("");
    try {
      const { data } = await axios.post("/api/activities", {
        expense_type:     expenseType,
        activity_id_desc: desc.trim() || null,
        account_id:       selectedAcct?.id ?? null,
      });
      setCreatedId(data.activity_id);
    } catch (e) {
      setErr(e?.response?.data?.detail ?? "Failed to create activity ID");
    } finally {
      setSaving(false);
    }
  }

  // Success state — show the generated ID
  if (createdId) {
    return (
      <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
        <div className="bg-white rounded-xl shadow-xl p-8 w-full max-w-sm text-center">
          <div className="text-4xl mb-3">✓</div>
          <h3 className="text-sm font-semibold text-gray-900 mb-1">Activity ID Created</h3>
          <p className="text-xs text-gray-400 mb-4">{row.entry_label}</p>
          <div className="bg-indigo-50 border border-indigo-200 rounded-lg px-4 py-3 mb-6">
            <p className="text-[10px] text-indigo-400 uppercase tracking-wide mb-0.5">Generated Activity ID</p>
            <p className="font-mono text-lg font-bold text-indigo-700">{createdId}</p>
          </div>
          <button
            onClick={() => { onSuccess(createdId); }}
            className="w-full px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
          >
            Done
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-xl overflow-y-auto max-h-[90vh]">
        <h3 className="text-sm font-semibold text-gray-900 mb-0.5">Create Activity ID</h3>
        <p className="text-xs text-gray-400 mb-4">Finalizing: {row.entry_label}</p>

        {/* Type + Description + ID preview */}
        <div className="grid grid-cols-2 gap-3 mb-4">
          <div>
            <label className={labelCls}>Expense Type</label>
            <div className="flex rounded-lg border border-gray-200 overflow-hidden text-sm">
              {["opex","capex"].map((t) => (
                <button
                  key={t}
                  onClick={() => setExpenseType(t)}
                  className={`flex-1 py-1.5 font-medium transition-colors ${
                    expenseType === t
                      ? "bg-indigo-600 text-white"
                      : "bg-white text-gray-500 hover:bg-gray-50"
                  }`}
                >
                  {t === "opex" ? "Opex" : "Capex"}
                </button>
              ))}
            </div>
            <p className="text-[10px] text-gray-400 mt-1">
              ID will be auto-generated as <span className="font-mono text-indigo-600">{prefix}-NNNNNNN</span>
            </p>
          </div>
          <div>
            <label className={labelCls}>Description</label>
            <input
              type="text" value={desc} onChange={(e) => setDesc(e.target.value)}
              placeholder="e.g. Acme Software subscription"
              className="w-full border border-gray-200 rounded-lg px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-300"
            />
          </div>
        </div>

        {/* Cascading filters */}
        <div className="mb-2">
          <p className={labelCls}>Filter accounts</p>
          <div className="grid grid-cols-3 gap-2 mb-2">
            <div>
              <p className="text-[10px] text-gray-400 mb-0.5">Cost Element</p>
              <select value={ceFilter} onChange={(e) => { setCeFilter(e.target.value); setAgFilter(""); setAsgFilter(""); setSelectedAcct(null); }} className={selectCls}>
                <option value="">All</option>
                {costElements.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <div>
              <p className="text-[10px] text-gray-400 mb-0.5">Account Group</p>
              <select value={agFilter} onChange={(e) => { setAgFilter(e.target.value); setAsgFilter(""); setSelectedAcct(null); }} className={selectCls}>
                <option value="">All</option>
                {accountGroups.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
            <div>
              <p className="text-[10px] text-gray-400 mb-0.5">Sub Group</p>
              <select value={asgFilter} onChange={(e) => { setAsgFilter(e.target.value); setSelectedAcct(null); }} className={selectCls}>
                <option value="">All</option>
                {subGroups.map((a) => <option key={a} value={a}>{a}</option>)}
              </select>
            </div>
          </div>
        </div>

        {/* Account list */}
        <div className="border border-gray-200 rounded-lg overflow-hidden mb-3">
          <div className="grid grid-cols-[1fr_1.5fr_1fr_1fr] gap-2 px-2 py-1 bg-gray-50 border-b border-gray-100 text-[10px] uppercase tracking-wide text-gray-400 font-medium">
            <span>Account #</span><span>Description</span><span>Sub Group</span><span>Cost Element</span>
          </div>
          <div className="max-h-44 overflow-y-auto divide-y divide-gray-50">
            {filteredAccounts.length === 0 && (
              <p className="text-xs text-gray-400 text-center py-4">No accounts match</p>
            )}
            {filteredAccounts.map((acct) => (
              <div key={acct.id} onClick={() => setSelectedAcct(acct)} className={rowCls(acct.id)}>
                <span className="font-mono">{acct.account_number}</span>
                <span className="truncate">{acct.account_desc ?? "—"}</span>
                <span className="truncate text-gray-400">{acct.account_sub_group}</span>
                <span className="text-gray-400">{acct.cost_element}</span>
              </div>
            ))}
          </div>
        </div>

        {selectedAcct && (
          <div className="text-xs bg-indigo-50 border border-indigo-200 rounded-lg px-3 py-2 mb-3 text-indigo-700">
            Selected: <span className="font-mono font-medium">{selectedAcct.account_number}</span>
            {" · "}{selectedAcct.account_group} › {selectedAcct.account_sub_group}
            {" · "}{selectedAcct.cost_element}
          </div>
        )}

        {err && <p className="text-xs text-red-500 mb-3">{err}</p>}

        <div className="flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700">Cancel</button>
          <button
            disabled={saving}
            onClick={handleCreate}
            className="px-4 py-1.5 text-sm bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:opacity-50"
          >
            {saving ? "Creating…" : "Create"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default function ControllablePage() {
  const [fiscalYear, setFiscalYear] = useState(CURRENT_YEAR + 1);
  const [selectedScenarioId, setSelectedScenarioId] = useState(null);

  // Client-side filters
  const [deptFilter, setDeptFilter] = useState([]);
  const [costElementFilter, setCostElementFilter] = useState([]);
  const [accountGroupFilter, setAccountGroupFilter] = useState([]);
  const [accountSubGroupFilter, setAccountSubGroupFilter] = useState([]);
  const [activityIdFilter, setActivityIdFilter] = useState([]);

  const [showNewRequest, setShowNewRequest] = useState(false);
  const [createActivityRow, setCreateActivityRow] = useState(null);

  const upsertEntry = useUpsertControllableEntry();

  const { data: scenarios, isLoading: scenariosLoading } = useScenarios(fiscalYear, "CONTROLLABLE");

  const effectiveScenarioId = useMemo(() => {
    if (selectedScenarioId && scenarios?.find((s) => s.id === selectedScenarioId)) {
      return selectedScenarioId;
    }
    return scenarios?.find((s) => s.is_baseline)?.id ?? scenarios?.[0]?.id ?? null;
  }, [selectedScenarioId, scenarios]);

  const { data: plan, isLoading: planLoading, isFetching } = useControllablePlan(fiscalYear, effectiveScenarioId);

  // Derive unique filter options from plan rows
  const filterOptions = useMemo(() => {
    if (!plan?.rows) return { depts: [], costElements: [], accountGroups: [], accountSubGroups: [], activityIds: [] };
    const rows = plan.rows;
    return {
      depts: [...new Set(rows.map((r) => r.department_name).filter(Boolean))].sort(),
      costElements: [...new Set(rows.map((r) => r.cost_element).filter(Boolean))].sort(),
      accountGroups: [...new Set(rows.map((r) => r.account_group).filter(Boolean))].sort(),
      accountSubGroups: [...new Set(rows.map((r) => r.account_sub_group).filter(Boolean))].sort(),
      activityIds: [...new Set(rows.map((r) => r.activity_id).filter(Boolean))].sort(),
    };
  }, [plan]);

  const filteredRows = useMemo(() => {
    if (!plan?.rows) return [];
    return plan.rows.filter((r) => {
      if (deptFilter.length > 0 && !deptFilter.includes(r.department_name)) return false;
      if (costElementFilter.length > 0 && !costElementFilter.includes(r.cost_element)) return false;
      if (accountGroupFilter.length > 0 && !accountGroupFilter.includes(r.account_group)) return false;
      if (accountSubGroupFilter.length > 0 && !accountSubGroupFilter.includes(r.account_sub_group)) return false;
      if (activityIdFilter.length > 0 && r.activity_id && !activityIdFilter.includes(r.activity_id)) return false;
      return true;
    });
  }, [plan, deptFilter, costElementFilter, accountGroupFilter, accountSubGroupFilter, activityIdFilter]);

  const kpis = useMemo(() => {
    const cf = filteredRows.reduce((s, r) => s + Number(r.current_and_forecast ?? 0), 0);
    // Budget plan: contracted amounts for EXISTING rows, q1-q4 amounts for NEW_REQUEST
    const budget = filteredRows.reduce((s, r) => {
      if (r.entry_category === "NEW_REQUEST") {
        return s + Number(r.q1_amount ?? 0) + Number(r.q2_amount ?? 0) + Number(r.q3_amount ?? 0) + Number(r.q4_amount ?? 0);
      }
      return s + Number(r.current_and_forecast ?? 0);
    }, 0);
    return { cf, budget, variance: budget - cf };
  }, [filteredRows]);

  const availableYears = [CURRENT_YEAR - 1, CURRENT_YEAR, CURRENT_YEAR + 1, CURRENT_YEAR + 2];

  function parseAmt(v) {
    const n = parseFloat(String(v ?? "").replace(/,/g, ""));
    return isNaN(n) ? null : n;
  }

  function handleAddNewRequest(form) {
    upsertEntry.mutate({
      scenario_id:     effectiveScenarioId,
      fiscal_year:     fiscalYear,
      activity_id:     null,
      entry_label:     form.label.trim(),
      entry_category:  "NEW_REQUEST",
      department_name: form.department || null,
      account_group:   form.accountGroup || null,
      account_sub_group: form.accountSubGroup || null,
      cost_element:    form.costElement || null,
      expense_type:    form.expenseType,
      q1_amount:       parseAmt(form.q1),
      q2_amount:       parseAmt(form.q2),
      q3_amount:       parseAmt(form.q3),
      q4_amount:       parseAmt(form.q4),
    }, {
      onSuccess: () => setShowNewRequest(false),
    });
  }

  const makeOptions = (arr) => arr.map((v) => ({ value: v, label: v }));

  return (
    <div className="space-y-2">
      {/* Row 1: Title + scenario selector + FY picker */}
      <div className="bg-white border border-gray-200 rounded-xl px-4 py-2.5 flex items-center gap-3 flex-wrap">
        <div className="shrink-0">
          <span className="text-sm font-semibold text-gray-900">Controllable Budget</span>
          <span className="ml-2 text-[11px] text-gray-400">Vendor &amp; contract costs by activity ID</span>
        </div>
        <div className="flex-1" />
        {!scenariosLoading && (
          <ScenarioPanel
            scenarios={scenarios ?? []}
            selectedId={effectiveScenarioId}
            onSelect={setSelectedScenarioId}
            fiscalYear={fiscalYear}
            budgetType="CONTROLLABLE"
            compact
          />
        )}
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-xs text-gray-400">FY:</span>
          <select
            value={fiscalYear}
            onChange={(e) => {
              setFiscalYear(Number(e.target.value));
              setSelectedScenarioId(null);
              setDeptFilter([]);
              setCostElementFilter([]);
              setAccountGroupFilter([]);
              setAccountSubGroupFilter([]);
              setActivityIdFilter([]);
            }}
            className="text-sm border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-300"
          >
            {availableYears.map((y) => (
              <option key={y} value={y}>FY{y}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Row 2: Filters + Actuals Cutoff + New Request button */}
      <div className="bg-white border border-gray-200 rounded-xl px-4 py-2 flex items-center gap-4 flex-wrap">
        <ActualsCutoffControl fiscalYear={fiscalYear} />
        <div className="w-px h-4 bg-gray-200 shrink-0" />
        {filterOptions.depts.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400 shrink-0">Dept:</span>
            <div className="w-36">
              <DropdownSlicer title="Department" options={makeOptions(filterOptions.depts)} selected={deptFilter} onToggle={setDeptFilter} />
            </div>
          </div>
        )}
        {filterOptions.accountGroups.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400 shrink-0">Acct Group:</span>
            <div className="w-36">
              <DropdownSlicer title="Account Group" options={makeOptions(filterOptions.accountGroups)} selected={accountGroupFilter} onToggle={setAccountGroupFilter} />
            </div>
          </div>
        )}
        {filterOptions.accountSubGroups.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400 shrink-0">Sub Group:</span>
            <div className="w-36">
              <DropdownSlicer title="Account Sub Group" options={makeOptions(filterOptions.accountSubGroups)} selected={accountSubGroupFilter} onToggle={setAccountSubGroupFilter} />
            </div>
          </div>
        )}
        {filterOptions.costElements.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400 shrink-0">Cost Element:</span>
            <div className="w-36">
              <DropdownSlicer title="Cost Element" options={makeOptions(filterOptions.costElements)} selected={costElementFilter} onToggle={setCostElementFilter} />
            </div>
          </div>
        )}
        {filterOptions.activityIds.length > 0 && (
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-gray-400 shrink-0">Activity ID:</span>
            <div className="w-44">
              <DropdownSlicer title="Activity ID" options={makeOptions(filterOptions.activityIds)} selected={activityIdFilter} onToggle={setActivityIdFilter} />
            </div>
          </div>
        )}
        <div className="flex-1" />
        {effectiveScenarioId && (
          <button
            onClick={() => setShowNewRequest(true)}
            className="text-xs px-3 py-1.5 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 whitespace-nowrap"
          >
            + New Controllable Request
          </button>
        )}
      </div>

      {/* Row 3: KPI strip */}
      {plan && (
        <div className="bg-white border border-gray-200 rounded-xl flex items-stretch divide-x divide-gray-100 overflow-hidden">
          <KpiCell label="Current+Forecast" value={fmtK(kpis.cf)} accent="text-emerald-700" />
          <KpiCell label="Budget Total" value={fmtK(kpis.budget)} accent="text-indigo-700" />
          <KpiCell
            label="Variance (Budget − C+F)"
            value={fmtFull.format(kpis.variance)}
            accent={kpis.variance > 0 ? "text-red-600" : kpis.variance < 0 ? "text-green-700" : "text-gray-500"}
          />
        </div>
      )}

      {/* Loading state */}
      {(planLoading || isFetching) && !plan && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
          Loading…
        </div>
      )}

      {/* No scenario */}
      {!effectiveScenarioId && !scenariosLoading && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
          No scenarios found for FY{fiscalYear}. Create one using the scenario panel above.
        </div>
      )}

      {/* Main table */}
      {effectiveScenarioId && plan && (
        <div className={isFetching ? "opacity-70 transition-opacity" : ""}>
          <ControllableTable
            rows={filteredRows}
            scenarioId={effectiveScenarioId}
            fiscalYear={fiscalYear}
            onCreateActivityId={(row) => setCreateActivityRow(row)}
          />
        </div>
      )}

      {/* Modals */}
      {showNewRequest && (
        <NewRequestModal
          onClose={() => setShowNewRequest(false)}
          onSubmit={handleAddNewRequest}
          loading={upsertEntry.isPending}
          filterOptions={filterOptions}
        />
      )}
      {createActivityRow && (
        <CreateActivityIdModal
          row={createActivityRow}
          onClose={() => setCreateActivityRow(null)}
          onSuccess={(createdId) => {
            upsertEntry.mutate({
              entry_id:       createActivityRow.entry_id,
              scenario_id:    effectiveScenarioId,
              fiscal_year:    fiscalYear,
              activity_id:    createdId,
              entry_label:    createActivityRow.entry_label,
              entry_category: createActivityRow.entry_category,
              department_name:    createActivityRow.department_name,
              account_group:      createActivityRow.account_group,
              account_sub_group:  createActivityRow.account_sub_group,
              cost_element:       createActivityRow.cost_element,
              expense_type:       createActivityRow.expense_type,
              q1_amount: createActivityRow.q1_amount,
              q2_amount: createActivityRow.q2_amount,
              q3_amount: createActivityRow.q3_amount,
              q4_amount: createActivityRow.q4_amount,
            }, { onSuccess: () => setCreateActivityRow(null) });
          }}
        />
      )}
    </div>
  );
}
