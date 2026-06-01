const fmtFull = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
const fmt = (v) => fmtFull.format(Number(v ?? 0));

const QUARTERS = ["q1", "q2", "q3", "q4"];
const Q_LABELS = { q1: "Q1", q2: "Q2", q3: "Q3", q4: "Q4" };

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

function AmountCell({ value, className = "" }) {
  return (
    <td className={`px-2 py-2 text-right font-mono text-xs tabular-nums text-gray-700 ${className}`}>
      {fmt(value)}
    </td>
  );
}

function DeltaCell({ value, pct, className = "" }) {
  return (
    <td className={`px-2 py-2 text-right font-mono text-xs tabular-nums ${deltaClass(value)} ${className}`}>
      <div>{fmtDelta(value)}</div>
      {pct !== undefined && Number(pct) !== 0 && (
        <div className="text-[10px] opacity-70">{fmtPct(pct)}</div>
      )}
    </td>
  );
}

function DataRow({ label, amountsA, amountsB, delta, rowClass = "" }) {
  return (
    <tr className={rowClass}>
      <td className="sticky left-0 z-10 px-4 py-2 text-xs text-gray-500 bg-inherit whitespace-nowrap pl-8">
        {label}
      </td>
      {QUARTERS.map((q) => (
        <>
          <AmountCell key={`${q}-a`} value={amountsA?.[q]} />
          <AmountCell key={`${q}-b`} value={amountsB?.[q]} />
          <DeltaCell  key={`${q}-d`} value={delta?.[q]} pct={delta?.[`${q}_pct`]} className="bg-gray-50/50" />
        </>
      ))}
      {/* FY Total */}
      <AmountCell value={amountsA?.annual} className="bg-indigo-50/30 font-semibold" />
      <AmountCell value={amountsB?.annual} className="bg-indigo-50/30 font-semibold" />
      <DeltaCell  value={delta?.annual} pct={delta?.annual_pct} className="bg-indigo-100/40 font-semibold" />
    </tr>
  );
}

function TotalRow({ label, amountsA, amountsB, delta }) {
  return (
    <tr className="bg-gray-100 border-b border-gray-200">
      <td className="sticky left-0 z-10 px-4 py-2.5 text-xs font-bold uppercase tracking-wide bg-gray-100 text-gray-800">
        {label}
      </td>
      {QUARTERS.map((q) => (
        <>
          <td key={`${q}-a`} className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900">
            {fmt(amountsA?.[q])}
          </td>
          <td key={`${q}-b`} className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900">
            {fmt(amountsB?.[q])}
          </td>
          <td key={`${q}-d`} className={`px-2 py-2.5 text-right font-mono text-xs tabular-nums bg-gray-50 ${deltaClass(delta?.[q])}`}>
            <div>{fmtDelta(delta?.[q])}</div>
            {Number(delta?.[`${q}_pct`] ?? 0) !== 0 && (
              <div className="text-[10px] opacity-70">{fmtPct(delta?.[`${q}_pct`])}</div>
            )}
          </td>
        </>
      ))}
      <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900 bg-indigo-50/50">
        {fmt(amountsA?.annual)}
      </td>
      <td className="px-2 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-gray-900 bg-indigo-50/50">
        {fmt(amountsB?.annual)}
      </td>
      <td className={`px-2 py-2.5 text-right font-mono text-xs tabular-nums bg-indigo-100/50 ${deltaClass(delta?.annual)}`}>
        <div>{fmtDelta(delta?.annual)}</div>
        {Number(delta?.annual_pct ?? 0) !== 0 && (
          <div className="text-[10px] opacity-70">{fmtPct(delta?.annual_pct)}</div>
        )}
      </td>
    </tr>
  );
}

export default function NcComparisonTable({ data, scenarioAName, scenarioBName }) {
  if (!data?.departments?.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
        No data to compare. Ensure both scenarios have entries.
      </div>
    );
  }

  const { departments, totals } = data;
  const aLabel = scenarioAName ?? "Scenario A";
  const bLabel = scenarioBName ?? "Scenario B";

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            {/* Row 1: Quarter group headers */}
            <tr className="bg-gray-50 border-b border-gray-200">
              <th rowSpan={2} className="sticky left-0 z-20 bg-gray-50 px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[220px] border-b border-gray-200">
                Department / Category
              </th>
              {QUARTERS.map((q) => (
                <th key={q} colSpan={3} className="px-2 py-2 text-center font-medium text-gray-500 uppercase tracking-wide border-l border-gray-200 min-w-[330px]">
                  {Q_LABELS[q]}
                </th>
              ))}
              <th colSpan={3} className="px-2 py-2 text-center font-medium text-indigo-600 uppercase tracking-wide border-l border-gray-200 bg-indigo-50/40 min-w-[330px]">
                FY Total
              </th>
            </tr>
            {/* Row 2: A / B / Δ sub-headers */}
            <tr className="bg-gray-50 border-b border-gray-200">
              {[...QUARTERS, "fy"].map((q) => (
                <>
                  <th key={`${q}-a`} className="px-2 py-1.5 text-right text-[10px] font-medium text-gray-400 border-l border-gray-200 min-w-[100px]">
                    {aLabel}
                  </th>
                  <th key={`${q}-b`} className="px-2 py-1.5 text-right text-[10px] font-medium text-gray-400 min-w-[100px]">
                    {bLabel}
                  </th>
                  <th key={`${q}-d`} className={`px-2 py-1.5 text-right text-[10px] font-medium text-gray-400 min-w-[90px] ${q === "fy" ? "bg-indigo-50/40" : "bg-gray-50/50"}`}>
                    Δ
                  </th>
                </>
              ))}
            </tr>
          </thead>

          <tbody>
            {departments.map((dept) => (
              <>
                <tr key={`${dept.department_name}-hdr`} className="bg-gray-50/80 border-t-2 border-gray-200">
                  <td
                    colSpan={3 * 5 + 1}
                    className="sticky left-0 px-4 py-2 text-xs font-semibold text-gray-800 uppercase tracking-wide bg-gray-50/80"
                  >
                    {dept.department_name}
                    {dept.department_code && (
                      <span className="ml-1.5 font-normal text-gray-400">({dept.department_code})</span>
                    )}
                  </td>
                </tr>
                <DataRow
                  key={`${dept.department_name}-rec`}
                  label="Approved Rec"
                  amountsA={dept.approved_rec_a}
                  amountsB={dept.approved_rec_b}
                  delta={dept.approved_rec_delta}
                  rowClass="border-b border-gray-100 bg-white"
                />
                <DataRow
                  key={`${dept.department_name}-ask`}
                  label="Additional Ask"
                  amountsA={dept.additional_ask_a}
                  amountsB={dept.additional_ask_b}
                  delta={dept.additional_ask_delta}
                  rowClass="border-b border-gray-100 bg-amber-50/10"
                />
                <DataRow
                  key={`${dept.department_name}-total`}
                  label="Net Total"
                  amountsA={dept.total_a}
                  amountsB={dept.total_b}
                  delta={dept.total_delta}
                  rowClass="border-b-2 border-gray-200 bg-white font-semibold"
                />
              </>
            ))}

            {/* Grand totals */}
            <TotalRow label="Grand Total — Approved Rec"    amountsA={totals?.approved_rec_a}   amountsB={totals?.approved_rec_b}   delta={totals?.approved_rec_delta} />
            <TotalRow label="Grand Total — Additional Ask"  amountsA={totals?.additional_ask_a} amountsB={totals?.additional_ask_b} delta={totals?.additional_ask_delta} />
            <TotalRow label="Grand Total — Net Total"       amountsA={totals?.total_a}          amountsB={totals?.total_b}          delta={totals?.total_delta} />
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
