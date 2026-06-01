import { useState, useMemo } from "react";
import { useScenarios, useNonControllablePlan } from "../../data/budget/hooks";
import ScenarioPanel from "./components/ScenarioPanel";
import CostElementFilter from "./components/CostElementFilter";
import ActualsCutoffControl from "./components/ActualsCutoffControl";
import NonControllableTable from "./components/NonControllableTable";
import WhatIfPanel from "./components/WhatIfPanel";
import AuditLogPanel from "./components/AuditLogPanel";
import DropdownSlicer from "../../components/DropdownSlicer";

const fmtCompact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
const fmtK = (v) => fmtCompact.format(Number(v ?? 0));

function KpiCard({ label, value, sub, accent }) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1.5">{label}</div>
      <div className={`text-xl font-semibold truncate ${accent || "text-gray-900"}`}>{value}</div>
      {sub && <div className="text-[10px] text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

const CURRENT_YEAR = new Date().getFullYear();

export default function NonControllablePage() {
  const [fiscalYear, setFiscalYear] = useState(CURRENT_YEAR + 1);
  const [selectedScenarioId, setSelectedScenarioId] = useState(null);
  const [deptFilter, setDeptFilter] = useState([]);   // empty = show all

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

  // Apply department filter to plan data (client-side)
  const filteredPlan = useMemo(() => {
    if (!plan) return null;
    if (deptFilter.length === 0) return plan;
    const depts = plan.departments.filter((d) => deptFilter.includes(d.department_name));

    // Recompute totals for filtered set
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

    // Split current into actuals vs forecast using the first dept's forecast map
    // (cutoff applies uniformly across all depts)
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
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Non-Controllable Budget</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Employee-related costs (salaries, travel, bonus, overtime) by department
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Fiscal Year:</span>
          <select
            value={fiscalYear}
            onChange={(e) => {
              setFiscalYear(Number(e.target.value));
              setSelectedScenarioId(null);
              setDeptFilter([]);
            }}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-300"
          >
            {availableYears.map((y) => (
              <option key={y} value={y}>FY{y}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Scenario panel */}
      {!scenariosLoading && (
        <ScenarioPanel
          scenarios={scenarios ?? []}
          selectedId={effectiveScenarioId}
          onSelect={setSelectedScenarioId}
          fiscalYear={fiscalYear}
        />
      )}

      {/* Filters */}
      <div className="bg-white border border-gray-200 rounded-xl p-4 space-y-3">
        <CostElementFilter fiscalYear={fiscalYear} />
        <ActualsCutoffControl fiscalYear={fiscalYear} />
        {deptOptions.length > 0 && (
          <div className="flex items-center gap-3">
            <span className="text-xs text-gray-400 shrink-0">Departments:</span>
            <div className="w-56">
              <DropdownSlicer
                title="Department"
                options={deptOptions}
                selected={deptFilter}
                onToggle={setDeptFilter}
              />
            </div>
          </div>
        )}
      </div>

      {/* KPI cards */}
      {kpis && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          <KpiCard
            label="Current — Actuals (FY)"
            value={fmtK(kpis.actualsAnnual)}
            sub="Confirmed spend from actuals"
            accent="text-emerald-700"
          />
          <KpiCard
            label="Current — Forecast (FY)"
            value={fmtK(kpis.forecastAnnual)}
            sub="Carry-forward estimate"
            accent="text-amber-600"
          />
          <KpiCard
            label="Total Approved Rec (FY)"
            value={fmtK(kpis.approvedAnnual)}
            sub="Sum of all approved rec amounts"
            accent="text-indigo-700"
          />
          <KpiCard
            label="Total Additional Ask (FY)"
            value={fmtK(kpis.askAnnual)}
            sub="Sum of all additional ask amounts"
            accent="text-amber-700"
          />
          <KpiCard
            label="Ask Delta"
            value={`${kpis.deltaPercent}%`}
            sub="Additional Ask ÷ Approved Rec"
            accent={Number(kpis.deltaPercent) > 10 ? "text-red-600" : "text-gray-900"}
          />
        </div>
      )}

      {/* Loading */}
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

      {/* Audit log */}
      {effectiveScenarioId && <AuditLogPanel scenarioId={effectiveScenarioId} />}

      {/* What-If panel */}
      {filteredPlan && <WhatIfPanel plan={filteredPlan} />}
    </div>
  );
}
