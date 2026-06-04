import { useState, useMemo } from "react";
import { useScenarios, useNonControllablePlan } from "../../data/budget/hooks";
import ScenarioPanel from "./components/ScenarioPanel";
import CostElementFilter from "./components/CostElementFilter";
import AccountGroupFilter from "./components/AccountGroupFilter";
import AccountSubGroupFilter from "./components/AccountSubGroupFilter";
import ActualsCutoffControl from "./components/ActualsCutoffControl";
import NonControllableTable from "./components/NonControllableTable";
import WhatIfPanel from "./components/WhatIfPanel";
import AuditLogPanel from "./components/AuditLogPanel";
import DropdownSlicer from "../../components/DropdownSlicer";

const fmtCompact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
const fmtK = (v) => fmtCompact.format(Number(v ?? 0));

function KpiCell({ label, value, accent }) {
  return (
    <div className="flex-1 px-4 py-2 text-center min-w-[100px]">
      <div className="text-[9px] text-gray-400 uppercase tracking-wide mb-0.5">{label}</div>
      <div className={`text-sm font-bold tabular-nums ${accent || "text-gray-900"}`}>{value}</div>
    </div>
  );
}

const CURRENT_YEAR = new Date().getFullYear();

export default function NonControllablePage() {
  const [fiscalYear, setFiscalYear] = useState(CURRENT_YEAR + 1);
  const [selectedScenarioId, setSelectedScenarioId] = useState(null);
  const [deptFilter, setDeptFilter] = useState([]);

  const { data: scenarios, isLoading: scenariosLoading } = useScenarios(fiscalYear, "NON_CONTROLLABLE");

  const effectiveScenarioId = useMemo(() => {
    if (selectedScenarioId && scenarios?.find((s) => s.id === selectedScenarioId)) {
      return selectedScenarioId;
    }
    return scenarios?.find((s) => s.is_baseline)?.id ?? scenarios?.[0]?.id ?? null;
  }, [selectedScenarioId, scenarios]);

  const { data: plan, isLoading: planLoading, isFetching } = useNonControllablePlan(
    fiscalYear,
    effectiveScenarioId
  );

  const filteredPlan = useMemo(() => {
    if (!plan) return null;
    if (deptFilter.length === 0) return plan;
    const depts = plan.departments.filter((d) => deptFilter.includes(d.department_name));

    const sum = (field, q) => depts.reduce((s, d) => s + Number(d[field]?.[q] ?? 0), 0);
    const makeQ = (field) => {
      const q1 = sum(field, "q1"), q2 = sum(field, "q2"),
            q3 = sum(field, "q3"), q4 = sum(field, "q4");
      return { q1, q2, q3, q4, annual: q1 + q2 + q3 + q4 };
    };

    return {
      ...plan,
      departments: depts,
      totals: {
        department_name: "__totals__",
        current_is_forecast: {},
        current: makeQ("current"),
        approved_rec: makeQ("approved_rec"),
        additional_ask: makeQ("additional_ask"),
      },
    };
  }, [plan, deptFilter]);

  const kpis = useMemo(() => {
    if (!filteredPlan?.totals) return null;
    const { current, approved_rec, additional_ask } = filteredPlan.totals;

    const forecastMap = filteredPlan.departments?.[0]?.current_is_forecast ?? {};
    const QS = ["q1", "q2", "q3", "q4"];
    const actualsAnnual = QS.filter((q) => !forecastMap[q]).reduce((s, q) => s + Number(current?.[q] ?? 0), 0);
    const forecastAnnual = QS.filter((q) => forecastMap[q]).reduce((s, q) => s + Number(current?.[q] ?? 0), 0);

    const approvedAnnual = Number(approved_rec?.annual ?? 0);
    const askAnnual = Number(additional_ask?.annual ?? 0);
    const delta = approvedAnnual > 0 ? ((askAnnual / approvedAnnual) * 100).toFixed(1) : "0.0";
    return { actualsAnnual, forecastAnnual, approvedAnnual, askAnnual, deltaPercent: delta };
  }, [filteredPlan]);

  const availableDepts = plan?.departments ?? [];
  const deptOptions = availableDepts.map((d) => ({
    value: d.department_name,
    label: d.department_code ? `${d.department_name} (${d.department_code})` : d.department_name,
  }));
  const availableYears = [CURRENT_YEAR - 1, CURRENT_YEAR, CURRENT_YEAR + 1, CURRENT_YEAR + 2];

  return (
    <div className="space-y-2">
      {/* Row 1: Title + scenario selector + FY picker */}
      <div className="bg-white border border-gray-200 rounded-xl px-4 py-2.5 flex items-center gap-3 flex-wrap">
        <div className="shrink-0">
          <span className="text-sm font-semibold text-gray-900">Non-Controllable Budget</span>
          <span className="ml-2 text-[11px] text-gray-400">Labor related cost by department</span>
        </div>
        <div className="flex-1" />
        {!scenariosLoading && (
          <ScenarioPanel
            scenarios={scenarios ?? []}
            selectedId={effectiveScenarioId}
            onSelect={setSelectedScenarioId}
            fiscalYear={fiscalYear}
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
            }}
            className="text-sm border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-300"
          >
            {availableYears.map((y) => (
              <option key={y} value={y}>FY{y}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Row 2: All filters in one horizontal line */}
      <div className="bg-white border border-gray-200 rounded-xl px-4 py-2 flex items-center gap-4 flex-wrap">
        <CostElementFilter fiscalYear={fiscalYear} />
        <div className="w-px h-4 bg-gray-200 shrink-0" />
        <AccountGroupFilter fiscalYear={fiscalYear} />
        <AccountSubGroupFilter fiscalYear={fiscalYear} />
        <div className="w-px h-4 bg-gray-200 shrink-0" />
        <ActualsCutoffControl fiscalYear={fiscalYear} />
        {deptOptions.length > 0 && (
          <>
            <div className="w-px h-4 bg-gray-200 shrink-0" />
            <div className="flex items-center gap-1.5">
              <span className="text-xs text-gray-400 shrink-0">Dept:</span>
              <div className="w-36">
                <DropdownSlicer
                  title="Department"
                  options={deptOptions}
                  selected={deptFilter}
                  onToggle={setDeptFilter}
                />
              </div>
            </div>
          </>
        )}
      </div>

      {/* Row 3: KPI strip */}
      {kpis && (
        <div className="bg-white border border-gray-200 rounded-xl flex items-stretch divide-x divide-gray-100 overflow-hidden">
          <KpiCell label="Actuals (FY)" value={fmtK(kpis.actualsAnnual)} accent="text-emerald-700" />
          <KpiCell label="Forecast (FY)" value={fmtK(kpis.forecastAnnual)} accent="text-amber-600" />
          <KpiCell label="Approved Rec" value={fmtK(kpis.approvedAnnual)} accent="text-indigo-700" />
          <KpiCell label="Additional Ask" value={fmtK(kpis.askAnnual)} accent="text-amber-700" />
          <KpiCell
            label="Ask Delta"
            value={`${kpis.deltaPercent}%`}
            accent={Number(kpis.deltaPercent) > 10 ? "text-red-600" : "text-gray-700"}
          />
        </div>
      )}

      {/* Loading state */}
      {(planLoading || isFetching) && !plan && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
          Loading…
        </div>
      )}

      {/* Main table */}
      {effectiveScenarioId && (
        <div className={isFetching && plan ? "opacity-70 transition-opacity" : ""}>
          <NonControllableTable plan={filteredPlan} scenarioId={effectiveScenarioId} />
        </div>
      )}

      {!effectiveScenarioId && !scenariosLoading && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
          No scenarios found for FY{fiscalYear}. The server will create a baseline on next startup.
        </div>
      )}

      {effectiveScenarioId && <AuditLogPanel scenarioId={effectiveScenarioId} />}
      {filteredPlan && <WhatIfPanel plan={filteredPlan} />}
    </div>
  );
}
