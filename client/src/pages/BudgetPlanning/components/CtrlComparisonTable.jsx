import { useState, Fragment } from "react";

const fmtFull = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
const fmt = (v) => fmtFull.format(Number(v ?? 0));

const QUARTERS = ["q1", "q2", "q3", "q4"];
const Q_LABELS = { q1: "Q1 (Jan–Mar)", q2: "Q2 (Apr–Jun)", q3: "Q3 (Jul–Sep)", q4: "Q4 (Oct–Dec)" };

function deltaClass(v) {
  const n = Number(v ?? 0);
  if (n > 0) return "text-red-600 font-semibold";
  if (n < 0) return "text-green-600 font-semibold";
  return "text-gray-400";
}

function fmtDelta(v) {
  const n = Number(v ?? 0);
  if (n === 0) return "—";
  return (n > 0 ? "+" : "") + fmt(n);
}

function fmtPct(v) {
  const n = Number(v ?? 0);
  if (n === 0) return "";
  return (n > 0 ? "+" : "") + n.toFixed(1) + "%";
}

function DataCells({ a, b, delta }) {
  return (
    <>
      {QUARTERS.map((q) => (
        <Fragment key={q}>
          <td className="px-2 py-2 text-right font-mono text-xs tabular-nums text-gray-700 border-l border-gray-100">{fmt(a?.[q])}</td>
          <td className="px-2 py-2 text-right font-mono text-xs tabular-nums text-gray-700">{fmt(b?.[q])}</td>
          <td className={`px-2 py-2 text-right font-mono text-xs tabular-nums bg-gray-50/50 ${deltaClass(delta?.[q])}`}>
            <div>{fmtDelta(delta?.[q])}</div>
            {Number(delta?.[`${q}_pct`] ?? 0) !== 0 && (
              <div className="text-[10px] opacity-70">{fmtPct(delta?.[`${q}_pct`])}</div>
            )}
          </td>
        </Fragment>
      ))}
      <td className="px-2 py-2 text-right font-mono text-xs tabular-nums text-gray-700 border-l border-indigo-100 bg-indigo-50/30">{fmt(a?.annual)}</td>
      <td className="px-2 py-2 text-right font-mono text-xs tabular-nums text-gray-700 bg-indigo-50/30">{fmt(b?.annual)}</td>
      <td className={`px-2 py-2 text-right font-mono text-xs tabular-nums bg-indigo-100/40 ${deltaClass(delta?.annual)}`}>
        <div>{fmtDelta(delta?.annual)}</div>
        {Number(delta?.annual_pct ?? 0) !== 0 && (
          <div className="text-[10px] opacity-70">{fmtPct(delta?.annual_pct)}</div>
        )}
      </td>
    </>
  );
}

function ActivityLabel({ row }) {
  const id = row.activity_id;
  const label = row.entry_label;
  const sub = row.account_sub_group || row.account_group;

  return (
    <div>
      {id
        ? <div className="font-mono text-[11px] font-semibold text-indigo-700">{id}</div>
        : <div className="text-xs text-amber-700 font-medium">New: {label}</div>
      }
      {sub && <div className="text-[10px] text-gray-400 mt-0.5 truncate max-w-[180px]">{sub}</div>}
    </div>
  );
}

export default function CtrlComparisonTable({ data, scenarioAName, scenarioBName }) {
  const [collapsed, setCollapsed] = useState(new Set());

  const departments = data?.departments ?? [];

  function toggleDept(name) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }
  function collapseAll() { setCollapsed(new Set(departments.map((d) => d.department_name))); }
  function expandAll()   { setCollapsed(new Set()); }

  if (!departments.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
        No data to compare. Ensure both scenarios have entries.
      </div>
    );
  }

  const { totals_a, totals_b, totals_delta } = data;
  const aLabel = scenarioAName ?? "Scenario A";
  const bLabel = scenarioBName ?? "Scenario B";

  // 1 activity col + 4Q×3 + 1FY×3 = 16 data cols
  const SUMMARY_COLSPAN = 15;

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      {/* Toolbar */}
      <div className="px-4 py-2 border-b border-gray-100 flex items-center gap-2">
        <span className="text-[11px] text-gray-400 mr-1">Departments:</span>
        <button
          onClick={expandAll}
          disabled={collapsed.size === 0}
          className="flex items-center gap-1 text-[11px] px-2 py-1 rounded border border-gray-200 text-gray-600 hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          Expand All
        </button>
        <button
          onClick={collapseAll}
          disabled={collapsed.size === departments.length}
          className="flex items-center gap-1 text-[11px] px-2 py-1 rounded border border-gray-200 text-gray-600 hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-3 h-3 rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          Collapse All
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th rowSpan={2} className="sticky left-0 z-20 bg-gray-50 px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[220px] border-r border-gray-200">
                Activity ID / Request
              </th>
              {QUARTERS.map((q) => (
                <th key={q} colSpan={3} className="px-2 py-2 text-center font-medium text-gray-500 uppercase tracking-wide border-l border-gray-200 min-w-[240px]">
                  {Q_LABELS[q]}
                </th>
              ))}
              <th colSpan={3} className="px-2 py-2 text-center font-medium text-indigo-600 uppercase tracking-wide border-l border-gray-200 bg-indigo-50/40 min-w-[240px]">
                FY Total
              </th>
            </tr>
            <tr className="bg-gray-50 border-b-2 border-gray-200">
              {[...QUARTERS, "fy"].map((q) => (
                <Fragment key={q}>
                  <th className="px-2 py-1.5 text-right text-[10px] font-medium text-gray-400 border-l border-gray-200 min-w-[75px]">{aLabel}</th>
                  <th className="px-2 py-1.5 text-right text-[10px] font-medium text-gray-400 min-w-[75px]">{bLabel}</th>
                  <th className={`px-2 py-1.5 text-right text-[10px] font-medium text-gray-400 min-w-[70px] ${q === "fy" ? "bg-indigo-50/40" : "bg-gray-50/50"}`}>Δ</th>
                </Fragment>
              ))}
            </tr>
          </thead>

          <tbody>
            {departments.map((dept, di) => {
              const isCollapsed = collapsed.has(dept.department_name);
              const borderTop = di > 0 ? "border-t-2 border-gray-200" : "";

              const deptCell = (rowSpan) => (
                <td
                  rowSpan={rowSpan}
                  className="sticky left-0 z-10 px-3 py-3 bg-white align-top border-r border-gray-100 select-none"
                >
                  <div className="flex items-start gap-1.5">
                    <svg
                      className={`w-3 h-3 mt-0.5 shrink-0 text-gray-400 transition-transform duration-150 ${isCollapsed ? "-rotate-90" : ""}`}
                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                    <div className="text-xs font-semibold text-gray-800">{dept.department_name}</div>
                  </div>
                </td>
              );

              if (isCollapsed) {
                const delta = Number(dept.total_b?.annual ?? 0) - Number(dept.total_a?.annual ?? 0);
                return (
                  <tr key={dept.department_name} className={`bg-gray-50/60 hover:bg-gray-100/60 ${borderTop}`} onClick={() => toggleDept(dept.department_name)}>
                    {deptCell(1)}
                    <td colSpan={SUMMARY_COLSPAN} className="px-3 py-2.5 text-[11px] text-gray-400 cursor-pointer">
                      <span className="text-gray-500">{aLabel}:</span>
                      <span className="ml-1 text-indigo-700 font-medium">{fmt(dept.total_a?.annual)}</span>
                      <span className="mx-2 text-gray-200">|</span>
                      <span className="text-gray-500">{bLabel}:</span>
                      <span className="ml-1 text-indigo-700 font-medium">{fmt(dept.total_b?.annual)}</span>
                      <span className="mx-2 text-gray-200">|</span>
                      <span className="text-gray-500">Δ:</span>
                      <span className={`ml-1 font-medium ${deltaClass(delta)}`}>{fmtDelta(delta)}</span>
                    </td>
                  </tr>
                );
              }

              const activityRows = dept.rows ?? [];
              return (
                <Fragment key={dept.department_name}>
                  {/* Activity rows */}
                  {activityRows.map((row, ri) => (
                    <tr key={row.activity_id ?? row.entry_label} onClick={() => toggleDept(dept.department_name)} className={`bg-white hover:bg-gray-50 cursor-pointer ${ri === 0 ? borderTop : "border-t border-gray-100"}`}>
                      {ri === 0 && deptCell(activityRows.length)}
                      <td className="px-3 py-2.5 border-r border-gray-100">
                        <ActivityLabel row={row} />
                      </td>
                      <DataCells a={row.budget_a} b={row.budget_b} delta={row.budget_delta} />
                    </tr>
                  ))}
                  {/* Dept subtotal */}
                  <tr className="bg-gray-50 border-t border-gray-200 font-semibold">
                    <td className="sticky left-0 z-[9] px-3 py-2 text-[11px] text-gray-500 uppercase tracking-wide border-r border-gray-100 bg-gray-50">Subtotal</td>
                    <td className="border-r border-gray-100" />
                    <DataCells a={dept.total_a} b={dept.total_b} delta={dept.total_delta} />
                  </tr>
                </Fragment>
              );
            })}

            {/* Grand total */}
            <tr className="bg-gray-100 border-t-2 border-gray-300">
              <td className="sticky left-0 z-10 px-4 py-3 bg-gray-100 border-r border-gray-200">
                <span className="text-xs font-bold text-gray-800 uppercase tracking-wide">Grand Total</span>
              </td>
              <td className="px-3 py-2.5 text-xs font-bold text-gray-800 border-r border-gray-100" />
              {QUARTERS.map((q) => (
                <Fragment key={q}>
                  <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900 border-l border-gray-200">{fmt(totals_a?.[q])}</td>
                  <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900">{fmt(totals_b?.[q])}</td>
                  <td className={`px-2 py-2.5 text-right font-mono text-xs tabular-nums bg-gray-50 ${deltaClass(totals_delta?.[q])}`}>
                    <div>{fmtDelta(totals_delta?.[q])}</div>
                    {Number(totals_delta?.[`${q}_pct`] ?? 0) !== 0 && (
                      <div className="text-[10px] opacity-70">{fmtPct(totals_delta?.[`${q}_pct`])}</div>
                    )}
                  </td>
                </Fragment>
              ))}
              <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900 border-l border-indigo-100 bg-indigo-50/50">{fmt(totals_a?.annual)}</td>
              <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900 bg-indigo-50/50">{fmt(totals_b?.annual)}</td>
              <td className={`px-2 py-2.5 text-right font-mono text-xs tabular-nums bg-indigo-100/50 ${deltaClass(totals_delta?.annual)}`}>
                <div>{fmtDelta(totals_delta?.annual)}</div>
                {Number(totals_delta?.annual_pct ?? 0) !== 0 && (
                  <div className="text-[10px] opacity-70">{fmtPct(totals_delta?.annual_pct)}</div>
                )}
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div className="px-4 py-2.5 border-t border-gray-100 flex items-center gap-4 text-[10px] text-gray-400">
        <span><span className="text-red-500 font-semibold">+Δ</span> = Scenario B costs more</span>
        <span><span className="text-green-600 font-semibold">−Δ</span> = Scenario B costs less</span>
      </div>
    </div>
  );
}
