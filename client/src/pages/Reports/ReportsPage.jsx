import { useState, useMemo } from "react";
import { useSpendSummary, downloadSpendCsv } from "../../data/spend";

// ─── Constants ────────────────────────────────────────────────────────────────

const CHART_COLORS = ["#185FA5", "#0F6E56", "#534AB7", "#993C1D", "#BA7517", "#0891B2"];
const CIRC = 226.19; // 2π × 36

const MONTH_LABELS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
const QUARTERS = [
  { label: "Q1", months: [1, 2, 3] },
  { label: "Q2", months: [4, 5, 6] },
  { label: "Q3", months: [7, 8, 9] },
  { label: "Q4", months: [10, 11, 12] },
];

function currentYear() { return new Date().getFullYear(); }
function currentMonth() { return new Date().getMonth() + 1; }
function currentQuarter() { return Math.ceil(currentMonth() / 3); }

// ─── Formatting ───────────────────────────────────────────────────────────────

function fmt(val) {
  const n = Number(val);
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `$${Math.round(n / 1_000)}K`;
  return `$${Math.round(n).toLocaleString()}`;
}

function fmtFull(val) {
  return `$${Number(val).toLocaleString("en-US", { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

// ─── Period → month_keys mapping ─────────────────────────────────────────────

function toMonthKeys(year, granularity, selMonths, selQuarters) {
  if (granularity === "monthly") {
    return selMonths.map(m => year * 100 + m);
  }
  if (granularity === "quarterly") {
    return selQuarters.flatMap(q => QUARTERS[q - 1].months.map(m => year * 100 + m));
  }
  // annual
  return Array.from({ length: 12 }, (_, i) => year * 100 + i + 1);
}

function toggleItem(arr, item) {
  return arr.includes(item) ? (arr.length > 1 ? arr.filter(x => x !== item) : arr) : [...arr, item].sort((a,b)=>a-b);
}

// ─── Insights computation ─────────────────────────────────────────────────────

function computeInsights(summary) {
  if (!summary) return [];
  const insights = [];
  const total = Number(summary.total_amount);

  // Month-over-month trend (need ≥ 2 months of data)
  if (summary.by_month.length >= 2) {
    const months = summary.by_month;
    const latest = Number(months[months.length - 1].amount);
    const prior  = Number(months[months.length - 2].amount);
    const pct    = prior > 0 ? ((latest - prior) / prior) * 100 : 0;
    const dir    = pct >= 0 ? "up" : "down";
    insights.push({
      icon: pct >= 0 ? "▲" : "▼",
      tone: pct >= 0 ? "amber" : "green",
      title: "Month-over-Month",
      body: `Spend ${dir} ${Math.abs(pct).toFixed(0)}% in ${months[months.length - 1].month_label} vs prior month`,
    });
  }

  // Vendor concentration risk
  if (summary.by_vendor.length > 0) {
    const top = summary.by_vendor[0];
    const tone = top.pct > 25 ? "red" : top.pct > 15 ? "amber" : "green";
    insights.push({
      icon: "◉",
      tone,
      title: "Vendor Concentration",
      body: `${top.label} is your largest vendor at ${top.pct.toFixed(0)}% of total spend (${fmt(top.amount)})`,
    });
  }

  // Top spending category
  if (summary.by_account_group.length > 0) {
    const top = summary.by_account_group[0];
    insights.push({
      icon: "●",
      tone: "blue",
      title: "Largest Category",
      body: `${top.label} leads at ${top.pct.toFixed(0)}% of spend — ${fmt(top.amount)} out of ${fmt(total)} total`,
    });
  }

  // Spend peak month
  if (summary.by_month.length > 1) {
    const peak = summary.by_month.reduce((a, b) => Number(a.amount) > Number(b.amount) ? a : b);
    insights.push({
      icon: "↑",
      tone: "blue",
      title: "Peak Month",
      body: `${peak.month_label} had the highest spend at ${fmtFull(peak.amount)}`,
    });
  }

  return insights;
}

const TONE = {
  red:   { bg: "bg-red-50",    border: "border-red-300",   icon: "text-red-500",   title: "text-red-700"   },
  amber: { bg: "bg-amber-50",  border: "border-amber-300", icon: "text-amber-500", title: "text-amber-700" },
  green: { bg: "bg-green-50",  border: "border-green-300", icon: "text-green-600", title: "text-green-700" },
  blue:  { bg: "bg-blue-50",   border: "border-blue-300",  icon: "text-blue-500",  title: "text-blue-700"  },
};

// ─── Sub-components ───────────────────────────────────────────────────────────

function Pill({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-2.5 py-1 rounded-md border transition-colors ${
        active
          ? "bg-indigo-600 border-indigo-600 text-white"
          : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
      }`}
    >
      {children}
    </button>
  );
}

function HBar({ label, amount, maxAmount, color }) {
  const w = maxAmount ? Math.max(2, (Number(amount) / maxAmount) * 100) : 2;
  return (
    <div className="flex items-center gap-2 mb-2 text-xs">
      <div className="w-28 text-right text-gray-500 shrink-0 truncate" title={label}>{label}</div>
      <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${w}%`, background: color }} />
      </div>
      <div className="w-14 text-gray-700 text-right shrink-0 font-medium">{fmt(amount)}</div>
    </div>
  );
}

function DonutChart({ byVendor, totalAmount }) {
  const top4      = byVendor.slice(0, 4);
  const top4Amt   = top4.reduce((s, v) => s + Number(v.amount), 0);
  const othersAmt = Number(totalAmount) - top4Amt;
  const othersPct = Math.max(0, 100 - top4.reduce((s, v) => s + v.pct, 0));
  const segments  = [
    ...top4.map(v => ({ label: v.label, pct: v.pct })),
    ...(othersAmt > 0 ? [{ label: "Others", pct: othersPct }] : []),
  ];
  let cum = 0;
  return (
    <div className="flex items-center gap-4">
      <svg width="90" height="90" viewBox="0 0 90 90" className="shrink-0">
        <circle cx="45" cy="45" r="36" fill="none" stroke="#F3F4F6" strokeWidth="16" />
        {segments.map((seg, i) => {
          const len = (seg.pct / 100) * CIRC;
          const offset = -cum;
          cum += len;
          return (
            <circle key={i} cx="45" cy="45" r="36" fill="none"
              stroke={CHART_COLORS[i] ?? "#9CA3AF"} strokeWidth="16"
              strokeDasharray={`${len} ${CIRC - len}`} strokeDashoffset={offset} />
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
  if (!byMonth?.length) return <div className="text-xs text-gray-400 mt-4">No data for this period</div>;
  const max = Math.max(...byMonth.map(m => Number(m.amount)));
  return (
    <div className="flex items-end gap-1.5 h-24 mt-2">
      {byMonth.map((m) => {
        const h = max ? Math.max(4, (Number(m.amount) / max) * 80) : 4;
        return (
          <div key={m.month_key} className="flex-1 flex flex-col items-center gap-1">
            <div className="w-full rounded-t transition-all" title={`${m.month_label}: ${fmtFull(m.amount)}`}
              style={{ height: `${h}px`, background: "#185FA5" }} />
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
        <div className="space-y-1.5"><Skeleton className="h-6 w-3/4" /><Skeleton className="h-3 w-1/2" /></div>
      ) : (
        <>
          <div className="text-xl font-semibold text-gray-900 truncate">{value}</div>
          {sub && <div className="text-[10px] text-gray-400 mt-0.5 truncate">{sub}</div>}
        </>
      )}
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

const YEARS = [currentYear() - 1, currentYear()];

export default function ReportsPage() {
  const [year,        setYear]        = useState(currentYear());
  const [granularity, setGranularity] = useState("monthly");
  const [selMonths,   setSelMonths]   = useState([currentMonth()]);
  const [selQuarters, setSelQuarters] = useState([currentQuarter()]);
  const [isExporting, setIsExporting] = useState(false);

  const monthKeys = useMemo(
    () => toMonthKeys(year, granularity, selMonths, selQuarters),
    [year, granularity, selMonths, selQuarters],
  );

  const filters = { month_keys: monthKeys };
  const { data: summary, isLoading } = useSpendSummary(filters);

  const insights  = useMemo(() => computeInsights(summary), [summary]);
  const topVendor = summary?.by_vendor?.[0];
  const topGroup  = summary?.by_account_group?.[0];
  const groupMax  = summary ? Math.max(...summary.by_account_group.map(g => Number(g.amount))) : 0;
  const deptMax   = summary ? Math.max(...summary.by_department.map(d => Number(d.amount))) : 0;
  const avgTxn    = summary?.total_transactions
    ? Number(summary.total_amount) / summary.total_transactions : 0;

  const handleExport = async () => {
    setIsExporting(true);
    try { await downloadSpendCsv(filters); }
    finally { setIsExporting(false); }
  };

  const switchGranularity = (g) => {
    setGranularity(g);
    // Reset sub-selection to current period when switching
    if (g === "monthly")   setSelMonths([currentMonth()]);
    if (g === "quarterly") setSelQuarters([currentQuarter()]);
  };

  // Label for period description in subtitle
  const periodLabel = useMemo(() => {
    if (granularity === "annual") return `Full Year ${year}`;
    if (granularity === "quarterly")
      return selQuarters.map(q => `Q${q}`).join(", ") + ` ${year}`;
    return selMonths.map(m => MONTH_LABELS[m - 1]).join(", ") + ` ${year}`;
  }, [year, granularity, selMonths, selQuarters]);

  return (
    <div className="p-6 space-y-5">

      {/* ── Header ── */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-base font-semibold text-gray-900">Spend Report</h1>
          <p className="text-xs text-gray-400 mt-0.5">{periodLabel}</p>
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

      {/* ── Period picker ── */}
      <div className="bg-white border border-gray-100 rounded-xl p-4 space-y-3">
        {/* Row 1: Year + Granularity */}
        <div className="flex items-center gap-4">
          <div className="flex gap-1">
            {YEARS.map(y => (
              <Pill key={y} active={year === y} onClick={() => setYear(y)}>{y}</Pill>
            ))}
          </div>
          <div className="w-px h-4 bg-gray-200" />
          <div className="flex gap-1">
            {["monthly", "quarterly", "annual"].map(g => (
              <Pill key={g} active={granularity === g} onClick={() => switchGranularity(g)}>
                {g.charAt(0).toUpperCase() + g.slice(1)}
              </Pill>
            ))}
          </div>
        </div>

        {/* Row 2: Sub-selection */}
        {granularity === "monthly" && (
          <div className="flex flex-wrap gap-1">
            {MONTH_LABELS.map((label, i) => {
              const m = i + 1;
              return (
                <Pill key={m} active={selMonths.includes(m)} onClick={() => setSelMonths(toggleItem(selMonths, m))}>
                  {label}
                </Pill>
              );
            })}
          </div>
        )}
        {granularity === "quarterly" && (
          <div className="flex gap-1">
            {QUARTERS.map((q, i) => (
              <Pill key={i} active={selQuarters.includes(i + 1)} onClick={() => setSelQuarters(toggleItem(selQuarters, i + 1))}>
                {q.label}
              </Pill>
            ))}
          </div>
        )}
        {granularity === "annual" && (
          <p className="text-xs text-gray-400">Showing all 12 months for {year}.</p>
        )}
      </div>

      {/* ── Insights ── */}
      {(isLoading || insights.length > 0) && (
        <div>
          <div className="text-[10px] text-gray-400 uppercase tracking-wider mb-2">Insights</div>
          <div className="grid grid-cols-2 gap-3">
            {isLoading
              ? [...Array(4)].map((_, i) => (
                  <div key={i} className="bg-white border border-gray-100 rounded-xl p-3 space-y-1.5">
                    <Skeleton className="h-3 w-1/3" />
                    <Skeleton className="h-3 w-full" />
                  </div>
                ))
              : insights.map((ins, i) => {
                  const t = TONE[ins.tone];
                  return (
                    <div key={i} className={`${t.bg} border ${t.border} rounded-xl p-3 flex gap-3`}>
                      <span className={`text-base leading-none mt-0.5 shrink-0 ${t.icon}`}>{ins.icon}</span>
                      <div>
                        <div className={`text-xs font-medium mb-0.5 ${t.title}`}>{ins.title}</div>
                        <div className="text-xs text-gray-600">{ins.body}</div>
                      </div>
                    </div>
                  );
                })
            }
          </div>
        </div>
      )}

      {/* ── KPI cards ── */}
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Total Spend"
          value={fmt(summary?.total_amount ?? 0)}
          sub={`${(summary?.total_transactions ?? 0).toLocaleString()} transactions`}
          loading={isLoading} />
        <KpiCard label="Avg per Transaction"
          value={fmt(avgTxn)}
          loading={isLoading} />
        <KpiCard label="Top Vendor"
          value={topVendor?.label ?? "—"}
          sub={topVendor ? `${fmt(topVendor.amount)} · ${topVendor.pct.toFixed(1)}% of spend` : null}
          loading={isLoading} />
        <KpiCard label="Largest Category"
          value={topGroup?.label ?? "—"}
          sub={topGroup ? `${fmt(topGroup.amount)} · ${topGroup.pct.toFixed(1)}% of spend` : null}
          loading={isLoading} />
      </div>

      {/* ── Charts row 1 ── */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs font-medium text-gray-800 mb-3">Spend by Account Group</div>
          {isLoading
            ? <div className="space-y-3">{[...Array(5)].map((_, i) => <Skeleton key={i} />)}</div>
            : (summary?.by_account_group ?? []).length === 0
              ? <p className="text-xs text-gray-400">No data for this period</p>
              : (summary.by_account_group).map((g, i) => (
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
          ) : (summary?.by_vendor ?? []).length === 0
            ? <p className="text-xs text-gray-400">No data for this period</p>
            : <DonutChart byVendor={summary.by_vendor} totalAmount={summary.total_amount} />
          }
        </div>
      </div>

      {/* ── Charts row 2 ── */}
      <div className="grid grid-cols-2 gap-4">
        <div className="bg-white border border-gray-100 rounded-xl p-4">
          <div className="text-xs font-medium text-gray-800 mb-3">Spend by Department</div>
          {isLoading
            ? <div className="space-y-3">{[...Array(6)].map((_, i) => <Skeleton key={i} />)}</div>
            : (summary?.by_department ?? []).length === 0
              ? <p className="text-xs text-gray-400">No data for this period</p>
              : (summary.by_department).map((d, i) => (
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
              {(summary?.by_month ?? []).length > 0 && (
                <div className="flex items-center gap-1.5 mt-3 text-[10px] text-gray-400">
                  <span className="w-3 h-3 rounded-sm inline-block" style={{ background: "#185FA5" }} />
                  Actual Spend
                </div>
              )}
            </>
          )}
        </div>
      </div>

    </div>
  );
}
