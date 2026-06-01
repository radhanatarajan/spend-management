import { useState, useMemo } from "react";
import { useScenarios, useScenarioComparison } from "../../data/budget/hooks";
import NcComparisonTable from "./components/NcComparisonTable";
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

export default function NcScenarioComparisonPage() {
  const [fiscalYear, setFiscalYear] = useState(CURRENT_YEAR + 1);
  const [scenarioAId, setScenarioAId] = useState(null);
  const [scenarioBId, setScenarioBId] = useState(null);
  const [deptFilter, setDeptFilter] = useState([]);

  const { data: scenarios } = useScenarios(fiscalYear, "NON_CONTROLLABLE");

  // Auto-select baseline as Scenario A on first load
  const effectiveAId = useMemo(() => {
    if (scenarioAId && scenarios?.find((s) => s.id === scenarioAId)) return scenarioAId;
    return scenarios?.find((s) => s.is_baseline)?.id ?? scenarios?.[0]?.id ?? null;
  }, [scenarioAId, scenarios]);

  const sameScenario = effectiveAId != null && scenarioBId != null && effectiveAId === scenarioBId;

  const { data: comparison, isLoading, isFetching } = useScenarioComparison(
    fiscalYear,
    effectiveAId,
    sameScenario ? null : scenarioBId
  );

  // Apply department filter client-side
  const filteredData = useMemo(() => {
    if (!comparison) return null;
    if (deptFilter.length === 0) return comparison;

    const depts = comparison.departments.filter((d) => deptFilter.includes(d.department_name));

    function sumAmounts(rows, field) {
      const q1 = rows.reduce((s, r) => s + Number(r[field]?.q1 ?? 0), 0);
      const q2 = rows.reduce((s, r) => s + Number(r[field]?.q2 ?? 0), 0);
      const q3 = rows.reduce((s, r) => s + Number(r[field]?.q3 ?? 0), 0);
      const q4 = rows.reduce((s, r) => s + Number(r[field]?.q4 ?? 0), 0);
      return { q1, q2, q3, q4, annual: q1 + q2 + q3 + q4 };
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

    const rec_a   = sumAmounts(depts, "approved_rec_a");
    const rec_b   = sumAmounts(depts, "approved_rec_b");
    const ask_a   = sumAmounts(depts, "additional_ask_a");
    const ask_b   = sumAmounts(depts, "additional_ask_b");
    const tot_a   = { q1: rec_a.q1+ask_a.q1, q2: rec_a.q2+ask_a.q2, q3: rec_a.q3+ask_a.q3, q4: rec_a.q4+ask_a.q4, annual: rec_a.annual+ask_a.annual };
    const tot_b   = { q1: rec_b.q1+ask_b.q1, q2: rec_b.q2+ask_b.q2, q3: rec_b.q3+ask_b.q3, q4: rec_b.q4+ask_b.q4, annual: rec_b.annual+ask_b.annual };

    return {
      ...comparison,
      departments: depts,
      totals: {
        department_name: "__totals__",
        approved_rec_a: rec_a,   approved_rec_b: rec_b,   approved_rec_delta: makeDelta(rec_a, rec_b),
        additional_ask_a: ask_a, additional_ask_b: ask_b, additional_ask_delta: makeDelta(ask_a, ask_b),
        total_a: tot_a,           total_b: tot_b,           total_delta: makeDelta(tot_a, tot_b),
      },
    };
  }, [comparison, deptFilter]);

  const kpis = useMemo(() => {
    if (!filteredData?.totals) return null;
    const { total_a, total_b, total_delta } = filteredData.totals;
    return {
      totalA: total_a?.annual,
      totalB: total_b?.annual,
      deltaAmt: total_delta?.annual,
      deltaPct: total_delta?.annual_pct,
    };
  }, [filteredData]);

  const scenarioAObj = scenarios?.find((s) => s.id === effectiveAId);
  const scenarioBObj = scenarios?.find((s) => s.id === scenarioBId);

  const deptOptions = (comparison?.departments ?? []).map((d) => ({
    value: d.department_name,
    label: d.department_code ? `${d.department_name} (${d.department_code})` : d.department_name,
  }));

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">NC Scenario Comparison</h2>
          <p className="text-xs text-gray-400 mt-0.5">
            Compare Non-Controllable budget amounts between two scenarios
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
            sub="Approved Rec + Additional Ask"
          />
          <KpiCard
            label={`${scenarioBObj?.name ?? "Scenario B"} — FY Total`}
            value={fmtK(kpis.totalB)}
            sub="Approved Rec + Additional Ask"
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

      {/* States */}
      {!scenarioBId && !sameScenario && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
          Select Scenario B above to start the comparison.
        </div>
      )}

      {(isLoading || isFetching) && scenarioBId && !sameScenario && !comparison && (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
          Loading comparison…
        </div>
      )}

      {/* Table */}
      {filteredData && !sameScenario && (
        <div className={isFetching && comparison ? "opacity-70 transition-opacity" : ""}>
          <NcComparisonTable
            data={filteredData}
            scenarioAName={scenarioAObj?.name}
            scenarioBName={scenarioBObj?.name}
          />
        </div>
      )}
    </div>
  );
}
