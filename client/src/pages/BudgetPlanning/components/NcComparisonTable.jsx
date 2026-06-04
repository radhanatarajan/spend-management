import { useState, Fragment } from "react";

const fmtFull = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
const fmt = (v) => fmtFull.format(Number(v ?? 0));

const QUARTERS = ["q1", "q2", "q3", "q4"];
const Q_LABELS = { q1: "Q1 (Jan–Mar)", q2: "Q2 (Apr–Jun)", q3: "Q3 (Jul–Sep)", q4: "Q4 (Oct–Dec)" };

// 1 category col + 4 quarter groups × 3 cols + 1 FY group × 3 cols = 16
const SUMMARY_COLSPAN = 16;

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

function DataCells({ amountsA, amountsB, delta }) {
  return (
    <>
      {QUARTERS.map((q) => (
        <Fragment key={q}>
          <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums text-gray-700 border-l border-gray-100">{fmt(amountsA?.[q])}</td>
          <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums text-gray-700">{fmt(amountsB?.[q])}</td>
          <td className={`px-2 py-2.5 text-right font-mono text-xs tabular-nums bg-gray-50/50 ${deltaClass(delta?.[q])}`}>
            <div>{fmtDelta(delta?.[q])}</div>
            {Number(delta?.[`${q}_pct`] ?? 0) !== 0 && (
              <div className="text-[10px] opacity-70">{fmtPct(delta?.[`${q}_pct`])}</div>
            )}
          </td>
        </Fragment>
      ))}
      <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums text-gray-700 border-l border-indigo-100 bg-indigo-50/30">{fmt(amountsA?.annual)}</td>
      <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums text-gray-700 bg-indigo-50/30">{fmt(amountsB?.annual)}</td>
      <td className={`px-2 py-2.5 text-right font-mono text-xs tabular-nums bg-indigo-100/40 ${deltaClass(delta?.annual)}`}>
        <div>{fmtDelta(delta?.annual)}</div>
        {Number(delta?.annual_pct ?? 0) !== 0 && (
          <div className="text-[10px] opacity-70">{fmtPct(delta?.annual_pct)}</div>
        )}
      </td>
    </>
  );
}

export default function NcComparisonTable({ data, scenarioAName, scenarioBName }) {
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

  const { totals } = data;
  const aLabel = scenarioAName ?? "Scenario A";
  const bLabel = scenarioBName ?? "Scenario B";

  const deptCell = (dept, rowSpan, isCollapsed) => (
    <td
      rowSpan={rowSpan}
      onClick={(e) => { e.stopPropagation(); toggleDept(dept.department_name); }}
      className="sticky left-0 z-10 px-3 py-3 bg-white align-top border-r border-gray-100 cursor-pointer select-none"
    >
      <div className="flex items-start gap-1.5">
        <svg
          className={`w-3 h-3 mt-0.5 shrink-0 text-gray-400 transition-transform duration-150 ${isCollapsed ? "-rotate-90" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
        <div>
          <div className="text-xs font-semibold text-gray-800">{dept.department_name}</div>
          {dept.department_code && (
            <div className="text-[10px] text-gray-400 mt-0.5">{dept.department_code}</div>
          )}
        </div>
      </div>
    </td>
  );

  const DEPT_ROWS = [
    { key: "rec",  label: "Approved Rec",   aKey: "approved_rec_a",   bKey: "approved_rec_b",   dKey: "approved_rec_delta",   rowClass: "bg-white" },
    { key: "ask",  label: "Additional Ask",  aKey: "additional_ask_a", bKey: "additional_ask_b", dKey: "additional_ask_delta", rowClass: "bg-amber-50/10 border-t border-gray-100" },
    { key: "tot",  label: "Net Total",       aKey: "total_a",          bKey: "total_b",           dKey: "total_delta",          rowClass: "bg-white border-t border-gray-100 font-semibold" },
  ];

  const TOTAL_ROWS = [
    { label: "Approved Rec",  aKey: "approved_rec_a",   bKey: "approved_rec_b",   dKey: "approved_rec_delta",   labelClass: "text-gray-800" },
    { label: "Additional Ask", aKey: "additional_ask_a", bKey: "additional_ask_b", dKey: "additional_ask_delta", labelClass: "text-amber-700" },
    { label: "Net Total",     aKey: "total_a",           bKey: "total_b",           dKey: "total_delta",          labelClass: "text-indigo-800" },
  ];

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      {/* Expand / Collapse toolbar */}
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
            {/* Row 1: Quarter group headers */}
            <tr className="bg-gray-50 border-b border-gray-200">
              <th rowSpan={2} className="sticky left-0 z-20 bg-gray-50 px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[200px] border-r border-gray-200">
                Department
              </th>
              <th rowSpan={2} className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[140px]">
                Category
              </th>
              {QUARTERS.map((q) => (
                <th key={q} colSpan={3} className="px-2 py-2 text-center font-medium text-gray-500 uppercase tracking-wide border-l border-gray-200 min-w-[270px]">
                  {Q_LABELS[q]}
                </th>
              ))}
              <th colSpan={3} className="px-2 py-2 text-center font-medium text-indigo-600 uppercase tracking-wide border-l border-gray-200 bg-indigo-50/40 min-w-[270px]">
                FY Total
              </th>
            </tr>
            {/* Row 2: A / B / Δ sub-headers */}
            <tr className="bg-gray-50 border-b-2 border-gray-200">
              {[...QUARTERS, "fy"].map((q) => (
                <Fragment key={q}>
                  <th className="px-2 py-1.5 text-right text-[10px] font-medium text-gray-400 border-l border-gray-200 min-w-[80px]">{aLabel}</th>
                  <th className="px-2 py-1.5 text-right text-[10px] font-medium text-gray-400 min-w-[80px]">{bLabel}</th>
                  <th className={`px-2 py-1.5 text-right text-[10px] font-medium text-gray-400 min-w-[75px] ${q === "fy" ? "bg-indigo-50/40" : "bg-gray-50/50"}`}>Δ</th>
                </Fragment>
              ))}
            </tr>
          </thead>

          <tbody>
            {departments.map((dept, di) => {
              const isCollapsed = collapsed.has(dept.department_name);
              const borderTop = di > 0 ? "border-t-2 border-gray-200" : "";

              if (isCollapsed) {
                const totalA = dept.total_a?.annual ?? 0;
                const totalB = dept.total_b?.annual ?? 0;
                const delta = totalB - totalA;
                return (
                  <Fragment key={dept.department_name}>
                    <tr className={`bg-gray-50/60 hover:bg-gray-100/60 ${borderTop}`} onClick={() => toggleDept(dept.department_name)}>
                      {deptCell(dept, 1, true)}
                      <td colSpan={SUMMARY_COLSPAN} className="px-3 py-2.5 text-[11px] text-gray-400 cursor-pointer">
                        <span className="text-gray-500">{aLabel}:</span>
                        <span className="ml-1 text-indigo-700 font-medium">{fmt(totalA)}</span>
                        <span className="mx-2 text-gray-200">|</span>
                        <span className="text-gray-500">{bLabel}:</span>
                        <span className="ml-1 text-indigo-700 font-medium">{fmt(totalB)}</span>
                        <span className="mx-2 text-gray-200">|</span>
                        <span className="text-gray-500">Δ:</span>
                        <span className={`ml-1 font-medium ${deltaClass(delta)}`}>{fmtDelta(delta)}</span>
                      </td>
                    </tr>
                  </Fragment>
                );
              }

              return (
                <Fragment key={dept.department_name}>
                  {DEPT_ROWS.map((row, ri) => (
                    <tr key={row.key} onClick={() => toggleDept(dept.department_name)} className={`${row.rowClass} ${ri === 0 ? borderTop : ""} cursor-pointer`}>
                      {ri === 0 && deptCell(dept, 3, false)}
                      <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap">{row.label}</td>
                      <DataCells amountsA={dept[row.aKey]} amountsB={dept[row.bKey]} delta={dept[row.dKey]} />
                    </tr>
                  ))}
                </Fragment>
              );
            })}

            {/* Grand Totals — Grand Total cell spans 3 rows */}
            {TOTAL_ROWS.map((row, ri) => (
              <tr key={row.label} className={`bg-gray-100 ${ri === 0 ? "border-t-2 border-gray-300" : "border-t border-gray-200"}`}>
                {ri === 0 && (
                  <td rowSpan={3} className="sticky left-0 z-10 px-4 py-3 bg-gray-100 align-middle border-r border-gray-200">
                    <span className="text-xs font-bold text-gray-800 uppercase tracking-wide">Grand Total</span>
                  </td>
                )}
                <td className={`px-3 py-2.5 text-xs font-bold uppercase tracking-wide ${row.labelClass}`}>{row.label}</td>
                {QUARTERS.map((q) => (
                  <Fragment key={q}>
                    <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900 border-l border-gray-200">{fmt(totals?.[row.aKey]?.[q])}</td>
                    <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900">{fmt(totals?.[row.bKey]?.[q])}</td>
                    <td className={`px-2 py-2.5 text-right font-mono text-xs tabular-nums bg-gray-50 ${deltaClass(totals?.[row.dKey]?.[q])}`}>
                      <div>{fmtDelta(totals?.[row.dKey]?.[q])}</div>
                      {Number(totals?.[row.dKey]?.[`${q}_pct`] ?? 0) !== 0 && (
                        <div className="text-[10px] opacity-70">{fmtPct(totals?.[row.dKey]?.[`${q}_pct`])}</div>
                      )}
                    </td>
                  </Fragment>
                ))}
                <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900 border-l border-indigo-100 bg-indigo-50/50">{fmt(totals?.[row.aKey]?.annual)}</td>
                <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900 bg-indigo-50/50">{fmt(totals?.[row.bKey]?.annual)}</td>
                <td className={`px-2 py-2.5 text-right font-mono text-xs tabular-nums bg-indigo-100/50 ${deltaClass(totals?.[row.dKey]?.annual)}`}>
                  <div>{fmtDelta(totals?.[row.dKey]?.annual)}</div>
                  {Number(totals?.[row.dKey]?.annual_pct ?? 0) !== 0 && (
                    <div className="text-[10px] opacity-70">{fmtPct(totals?.[row.dKey]?.annual_pct)}</div>
                  )}
                </td>
              </tr>
            ))}
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
