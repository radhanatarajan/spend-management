import { useState, useMemo } from "react";
import { useSpendSummary, downloadSpendCsv } from "../../data/spend";

const CHART_COLORS = [
  "#185FA5", "#0F6E56", "#534AB7", "#993C1D", "#BA7517", "#0891B2",
];

const CIRC = 226.19; // 2π × 36

function fmtAmount(val) {
  const n = Number(val);
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n).toLocaleString()}`;
}

function fmtFull(val) {
  return `$${Number(val).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function lastNMonths(n) {
  const now = new Date();
  let year = now.getFullYear(), month = now.getMonth() + 1;
  const keys = [];
  for (let i = 0; i < n; i++) {
    keys.push(year * 100 + month);
    if (--month === 0) { month = 12; year--; }
  }
  return keys;
}

const PERIODS = [
  { label: "Last Month", key: "1m",  getKeys: () => lastNMonths(1) },
  { label: "Last 3M",    key: "3m",  getKeys: () => lastNMonths(3) },
  { label: "Last 6M",    key: "6m",  getKeys: () => lastNMonths(6) },
  { label: "All Time",   key: "all", getKeys: () => null },
];

function HBar({ label, amount, maxAmount, color }) {
  const w = maxAmount ? Math.max(2, (Number(amount) / maxAmount) * 100) : 2;
  return (
    <div className="flex items-center gap-2 mb-2 text-xs">
      <div className="w-28 text-right text-gray-500 shrink-0 truncate" title={label}>{label}</div>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all" style={{ width: `${w}%`, background: color }} />
      </div>
      <div className="w-14 text-gray-700 text-right shrink-0 font-medium">{fmtAmount(amount)}</div>
    </div>
  );
}

function DonutChart({ byVendor, totalAmount }) {
  const total = Number(totalAmount);
  const top4 = byVendor.slice(0, 4);
  const top4Total = top4.reduce((s, v) => s + Number(v.amount), 0);
  const othersAmt = total - top4Total;
  const othersPct = Math.max(0, 100 - top4.reduce((s, v) => s + v.pct, 0));
  const segments = [
    ...top4.map(v => ({ label: v.label, pct: v.pct })),
    ...(othersAmt > 0 ? [{ label: "Others", pct: othersPct }] : []),
  ];

  let cumulative = 0;
  return (
    <div className="flex items-center gap-4">
      <svg width="90" height="90" viewBox="0 0 90 90" className="shrink-0">
        <circle cx="45" cy="45" r="36" fill="none" stroke="#F3F4F6" strokeWidth="16" />
        {segments.map((seg, i) => {
          const len = (seg.pct / 100) * CIRC;
          const dashArray = `${len} ${CIRC - len}`;
          const dashOffset = -cumulative;
          cumulative += len;
          return (
            <circle
              key={i}
              cx="45" cy="45" r="36"
              fill="none"
              stroke={CHART_COLORS[i] ?? "#9CA3AF"}
              strokeWidth="16"
              strokeDasharray={dashArray}
              strokeDashoffset={dashOffset}
            />
          );
        })}
      </svg>
      <div className="flex-1 space-y-2">
        {segments.map((seg, i) => (
          <div key={i} className="flex items-center gap-2 text-xs text-gray-500">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: CHART_COLORS[i] ?? "#9CA3AF" }} />
            <span className="flex-1 truncate">{seg.label}</span>
            <span className="font-medium text-gray-800">{seg.pct.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function MonthBars({ byMonth }) {
  if (!byMonth?.length) return <div className="text-xs text-gray-400 mt-4">No data</div>;
  const max = Math.max(...byMonth.map(m => Number(m.amount)));
  return (
    <div className="flex items-end gap-1.5 h-24 mt-2">
      {byMonth.map((m) => {
        const h = max ? Math.max(4, (Number(m.amount) / max) * 80) : 4;
        return (
          <div key={m.month_key} className="flex-1 flex flex-col items-center gap-1">
            <div
              className="w-full rounded-t transition-all"
              style={{ height: `${h}px`, background: "#185FA5" }}
              title={`${m.month_label}: ${fmtFull(m.amount)}`}
            />
            <span className="text-[9px] text-gray-400">{m.month_label.slice(0, 3)}</span>
          </div>
        );
      })}
    </div>
  );
}

function Skeleton({ className = "h-4 w-full" }) {
  return <div className={`animate-pulse bg-gray-200 rounded ${className}`} />;
}

function KpiCard({ label, value, sub, loading }) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1.5">{label}</div>
      {loading ? (
        <div className="space-y-1.5">
          <Skeleton className="h-6 w-3/4" />
          <Skeleton className="h-3 w-1/2" />
        </div>
      ) : (
        <>
          <div className="text-xl font-semibold text-gray-900 truncate">{value}</div>
          {sub && <div className="text-[10px] text-gray-400 mt-0.5 truncate">{sub}</div>}
        </>
      )}
    </div>
  );
}

export default function ReportsPage() {
  const [period, setPeriod] = useState("6m");
  const [isExporting, setIsExporting] = useState(false);

  const filters = useMemo(() => {
    const p = PERIODS.find(p => p.key === period);
    const keys = p?.getKeys() ?? null;
    return keys ? { month_keys: keys } : {};
  }, [period]);

  const { data: summary, isLoading } = useSpendSummary(filters);

  const handleExport = async () => {
    setIsExporting(true);
    try {
      await downloadSpendCsv(filters);
    } finally {
      setIsExporting(false);
    }
  };

  const topVendor = summary?.by_vendor?.[0];
  const topGroup  = summary?.by_account_group?.[0];
  const groupMax  = summary ? Math.max(...summary.by_account_group.map(g => Number(g.amount))) : 0;
  const deptMax   = summary ? Math.max(...summary.by_department.map(d => Number(d.amount))) : 0;
  const avgTxn    = summary?.total_transactions
    ? Number(summary.total_amount) / summary.total_transactions
    : 0;

  return (
    <div className="p-6 space-y-5">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-gray-900">Spend Reports</h1>
          <p className="text-xs text-gray-400 mt-0.5">Aggregated spend analytics</p>
        </div>
        <button
          onClick={handleExport}
          disabled={isExporting || isLoading}
          className="flex items-center gap-1.5 text-xs px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-gray-700 hover:bg-gray-50 disabled:opacity-50 transition-colors"
        >
          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
          </svg>
          {isExporting ? "Exporting…" : "Export CSV"}
        </button>
      </div>

      {/* Period selector */}
      <div className="flex gap-1.5">
        {PERIODS.map(p => (
          <button
            key={p.key}
            onClick={() => setPeriod(p.key)}
            className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
              period === p.key
                ? "bg-indigo-600 border-indigo-600 text-white"
                : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>

      {/* KPI cards */}
      <div className="grid grid-cols-4 gap-3">
        <KpiCard
          label="Total Spend"
          value={fmtAmount(summary?.total_amount ?? 0)}
          sub={`${(summary?.total_transactions ?? 0).toLocaleString()} transactions`}
          loading={isLoading}
        />
        <KpiCard
          label="Avg per Transaction"
          value={fmtAmount(avgTxn)}
          loading={isLoading}
        />
        <KpiCard
          label="Top Vendor"
          value={topVendor?.label ?? "—"}
          sub={topVendor ? `${fmtAmount(topVendor.amount)} · ${topVendor.pct.toFixed(1)}% of spend` : null}
          loading={isLoading}
        />
        <KpiCard
          label="Largest Category"
          value={topGroup?.label ?? "—"}
          sub={topGroup ? `${fmtAmount(topGroup.amount)} · ${topGroup.pct.toFixed(1)}% of spend` : null}
          loading={isLoading}
        />
      </div>

      {/* Row 2: Account Group bars + Vendor donut */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs font-medium text-gray-800 mb-3">Spend by Account Group</div>
          {isLoading
            ? <div className="space-y-3">{[...Array(5)].map((_, i) => <Skeleton key={i} />)}</div>
            : (summary?.by_account_group ?? []).map((g, i) => (
                <HBar key={g.label} label={g.label} amount={g.amount}
                  maxAmount={groupMax} color={CHART_COLORS[i % CHART_COLORS.length]} />
              ))
          }
        </div>

        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs font-medium text-gray-800 mb-3">Vendor Concentration</div>
          {isLoading ? (
            <div className="flex items-center gap-4">
              <div className="w-[90px] h-[90px] rounded-full bg-gray-100 animate-pulse shrink-0" />
              <div className="flex-1 space-y-2">{[...Array(4)].map((_, i) => <Skeleton key={i} />)}</div>
            </div>
          ) : (
            <DonutChart byVendor={summary?.by_vendor ?? []} totalAmount={summary?.total_amount ?? 0} />
          )}
        </div>
      </div>

      {/* Row 3: Department bars + Month trend */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs font-medium text-gray-800 mb-3">Spend by Department</div>
          {isLoading
            ? <div className="space-y-3">{[...Array(6)].map((_, i) => <Skeleton key={i} />)}</div>
            : (summary?.by_department ?? []).map((d, i) => (
                <HBar key={d.label} label={d.label} amount={d.amount}
                  maxAmount={deptMax} color={CHART_COLORS[i % CHART_COLORS.length]} />
              ))
          }
        </div>

        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs font-medium text-gray-800 mb-1">Spend by Month</div>
          {isLoading ? (
            <div className="flex items-end gap-1.5 h-24 mt-2">
              {[...Array(6)].map((_, i) => (
                <div key={i} className="flex-1 bg-gray-200 rounded-t animate-pulse"
                  style={{ height: `${30 + i * 8}px` }} />
              ))}
            </div>
          ) : (
            <>
              <MonthBars byMonth={summary?.by_month ?? []} />
              <div className="flex items-center gap-1.5 mt-3 text-[10px] text-gray-400">
                <span className="w-3 h-3 rounded-sm inline-block" style={{ background: "#185FA5" }} />
                Actual Spend
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
