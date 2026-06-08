import { useState, useMemo } from "react";
import { useScenarios, useControllableComparison } from "../../data/budget/hooks";
import CtrlComparisonTable from "./components/CtrlComparisonTable";
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
const AVAILABLE_YEARS = [CURRENT_YEAR - 1, CURRENT_YEAR, CURRENT_YEAR + 1, CURRENT_YEAR + 2];

export default function CtrlScenarioComparisonPage() {
  const [fiscalYear, setFiscalYear] = useState(CURRENT_YEAR + 1);
  const [scenarioAId, setScenarioAId] = useState(null);
  const [scenarioBId, setScenarioBId] = useState(null);
  const [deptFilter, setDeptFilter] = useState([]);

  const { data: scenarios } = useScenarios(fiscalYear, "CONTROLLABLE");

  const effectiveAId = useMemo(() => {
    if (scenarioAId && scenarios?.find((s) => s.id === scenarioAId)) return scenarioAId;
    return scenarios?.find((s) => s.is_baseline)?.id ?? scenarios?.[0]?.id ?? null;
  }, [scenarioAId, scenarios]);

  const sameScenario = effectiveAId != null && scenarioBId != null && effectiveAId === scenarioBId;

  const { data: comparison, isLoading, isFetching } = useControllableComparison(
    fiscalYear,
    effectiveAId,
    sameScenario ? null : scenarioBId,
  );

  const filteredData = useMemo(() => {
    if (!comparison) return null;
    if (deptFilter.length === 0) return comparison;

    const departments = comparison.departments.filter((d) => deptFilter.includes(d.department_name));

    function sumAmounts(rows, field) {
      return rows.reduce(
        (acc, r) => {
          const a = r[field];
          return { q1: acc.q1 + Number(a?.q1 ?? 0), q2: acc.q2 + Number(a?.q2 ?? 0), q3: acc.q3 + Number(a?.q3 ?? 0), q4: acc.q4 + Number(a?.q4 ?? 0), annual: acc.annual + Number(a?.annual ?? 0) };
        },
        { q1: 0, q2: 0, q3: 0, q4: 0, annual: 0 },
      );
    }

    function makeDelta(a, b) {
      const pct = (av, bv) => av !== 0 ? +((bv - av) / av * 100).toFixed(2) : 0;
      return {
        q1: b.q1 - a.q1, q2: b.q2 - a.q2, q3: b.q3 - a.q3, q4: b.q4 - a.q4,
        annual: b.annual - a.annual,
        q1_pct: pct(a.q1, b.q1), q2_pct: pct(a.q2, b.q2),
        q3_pct: pct(a.q3, b.q3), q4_pct: pct(a.q4, b.q4),
        annual_pct: pct(a.annual, b.annual),
      };
    }

    const ta = sumAmounts(departments, "total_a");
    const tb = sumAmounts(departments, "total_b");
    return {
      ...comparison,
      departments,
      totals_a: ta,
      totals_b: tb,
      totals_delta: makeDelta(ta, tb),
    };
  }, [comparison, deptFilter]);

  const kpis = useMemo(() => {
    if (!filteredData) return null;
    const { totals_a, totals_b, totals_delta } = filteredData;
    return {
      totalA: totals_a?.annual,
      totalB: totals_b?.annual,
      deltaAmt: totals_delta?.annual,
      deltaPct: totals_delta?.annual_pct,
    };
  }, [filteredData]);

  const scenarioAObj = scenarios?.find((s) => s.id === effectiveAId);
  const scenarioBObj = scenarios?.find((s) => s.id === scenarioBId);

  const deptOptions = (comparison?.departments ?? []).map((d) => ({
    value: d.department_name,
    label: d.department_name,
  }));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Controllable Scenario Comparison</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Compare Controllable budget plan amounts between two scenarios
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Fiscal Year:</span>
          <select
            value={fiscalYear}
            onChange={(e) => { setFiscalYear(Number(e.target.value)); setScenarioAId(null); setScenarioBId(null); setDeptFilter([]); }}
            className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-300"
          >
            {AVAILABLE_YEARS.map((y) => <option key={y} value={y}>FY{y}</option>)}
          </select>
        </div>
      </div>

      {/* Scenario selectors + dept filter */}
      <div className="bg-white border border-gray-200 rounded-xl p-4">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400 shrink-0">Scenario A:</span>
            <select
              value={effectiveAId ?? ""}
              onChange={(e) => setScenarioAId(Number(e.target.value) || null)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-300 min-w-[180px]"
            >
              {scenarios?.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          <span className="text-sm font-medium text-gray-400">vs</span>

          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400 shrink-0">Scenario B:</span>
            <select
              value={scenarioBId ?? ""}
              onChange={(e) => setScenarioBId(Number(e.target.value) || null)}
              className="text-sm border border-gray-200 rounded-lg px-3 py-1.5 focus:outline-none focus:ring-2 focus:ring-indigo-300 min-w-[180px]"
            >
              <option value="">— select —</option>
              {scenarios?.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </div>

          {deptOptions.length > 0 && (
            <div className="flex items-center gap-2 ml-auto">
              <span className="text-xs text-gray-400 shrink-0">Departments:</span>
              <div className="w-48">
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

        {sameScenario && (
          <p className="mt-2 text-xs text-amber-600">
            Scenario A and Scenario B are the same — please select two different scenarios to compare.
          </p>
        )}
      </div>

      {/* KPI cards */}
      {kpis && (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <KpiCard
            label={`${scenarioAObj?.name ?? "Scenario A"} — FY Total`}
            value={fmtK(kpis.totalA)}
            sub="Budget plan total"
          />
          <KpiCard
            label={`${scenarioBObj?.name ?? "Scenario B"} — FY Total`}
            value={fmtK(kpis.totalB)}
            sub="Budget plan total"
          />
          <KpiCard
            label="Variance ($)"
            value={kpis.deltaAmt != null ? (Number(kpis.deltaAmt) >= 0 ? "+" : "") + fmtK(kpis.deltaAmt) : "—"}
            sub="B minus A"
            accent={Number(kpis.deltaAmt ?? 0) > 0 ? "text-red-600" : Number(kpis.deltaAmt ?? 0) < 0 ? "text-green-600" : "text-gray-400"}
          />
          <KpiCard
            label="Variance (%)"
            value={kpis.deltaPct != null ? (Number(kpis.deltaPct) >= 0 ? "+" : "") + Number(kpis.deltaPct).toFixed(1) + "%" : "—"}
            sub="B vs A"
            accent={Number(kpis.deltaPct ?? 0) > 0 ? "text-red-600" : Number(kpis.deltaPct ?? 0) < 0 ? "text-green-600" : "text-gray-400"}
          />
        </div>
      )}

      {!scenarioBId && !sameScenario && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
          Select Scenario B above to start the comparison.
        </div>
      )}

      {(isLoading || isFetching) && scenarioBId && !sameScenario && !comparison && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400 animate-pulse">
          Loading comparison…
        </div>
      )}

      {filteredData && !sameScenario && (
        <div className={isFetching && comparison ? "opacity-70 transition-opacity" : ""}>
          <CtrlComparisonTable
            data={filteredData}
            scenarioAName={scenarioAObj?.name}
            scenarioBName={scenarioBObj?.name}
          />
        </div>
      )}
    </div>
  );
}
