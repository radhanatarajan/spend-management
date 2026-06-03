import { useState, useMemo } from "react";
import { useBudgetAuditReport } from "../../data/budget/hooks";
import DropdownSlicer from "../../components/DropdownSlicer";

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmtCompact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
const fmtK   = (v) => v != null ? fmtCompact.format(Number(v)) : "—";

function fmtDate(iso) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

const ENTRY_TYPE_LABELS = { APPROVED_REC: "Approved Rec", ADDITIONAL_ASK: "Additional Ask" };
const STATUS_COLORS = {
  DRAFT:            "bg-gray-100 text-gray-600",
  READY_FOR_REVIEW: "bg-blue-50 text-blue-700",
  APPROVED:         "bg-green-50 text-green-700",
  FINAL:            "bg-purple-50 text-purple-700",
  CANCELLED:        "bg-red-50 text-red-500",
};

function StatusBadge({ value }) {
  if (!value) return <span className="text-gray-300">—</span>;
  return (
    <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[value] ?? "bg-gray-100 text-gray-500"}`}>
      {value}
    </span>
  );
}

function AmountDiff({ oldVal, newVal }) {
  if (oldVal == null && newVal == null) return <span className="text-gray-200">—</span>;
  const changed = String(oldVal) !== String(newVal);
  return (
    <div className="text-right font-mono text-[11px] tabular-nums leading-tight">
      {changed ? (
        <>
          <div className="text-gray-400 line-through">{fmtK(oldVal)}</div>
          <div className="text-indigo-700 font-semibold">{fmtK(newVal)}</div>
        </>
      ) : (
        <div className="text-gray-500">{fmtK(newVal ?? oldVal)}</div>
      )}
    </div>
  );
}

function Pill({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-2.5 py-1 rounded-md border transition-colors whitespace-nowrap ${
        active
          ? "bg-indigo-600 border-indigo-600 text-white"
          : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
      }`}
    >
      {children}
    </button>
  );
}

// ── KPI card ──────────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub, accent }) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1.5">{label}</div>
      <div className={`text-xl font-semibold truncate ${accent || "text-gray-900"}`}>{value}</div>
      {sub && <div className="text-[10px] text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Table ─────────────────────────────────────────────────────────────────────

function AuditTable({ rows }) {
  if (!rows.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
        No audit events match the current filters.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="sticky left-0 z-10 bg-gray-50 px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[160px]">
                When
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[140px]">
                Scenario
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[120px]">
                Department
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[110px]">
                Category
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[90px]">
                Event
              </th>
              <th className="px-3 py-3 text-right font-medium text-gray-500 uppercase tracking-wide min-w-[90px]">
                Q1
              </th>
              <th className="px-3 py-3 text-right font-medium text-gray-500 uppercase tracking-wide min-w-[90px]">
                Q2
              </th>
              <th className="px-3 py-3 text-right font-medium text-gray-500 uppercase tracking-wide min-w-[90px]">
                Q3
              </th>
              <th className="px-3 py-3 text-right font-medium text-gray-500 uppercase tracking-wide min-w-[90px]">
                Q4
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[180px]">
                Status
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[140px]">
                Changed By
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row) => {
              const isAmount = row.event_type === "AMOUNT_CHANGED";
              return (
                <tr key={row.audit_id} className="hover:bg-gray-50 group">
                  <td className="sticky left-0 z-10 bg-white group-hover:bg-gray-50 px-4 py-2.5 whitespace-nowrap text-gray-500">
                    {fmtDate(row.changed_at)}
                  </td>
                  <td className="px-3 py-2.5 text-gray-700 truncate max-w-[160px]" title={row.scenario_name}>
                    {row.scenario_name}
                  </td>
                  <td className="px-3 py-2.5 text-gray-700">{row.department_name}</td>
                  <td className="px-3 py-2.5 text-gray-500">
                    {ENTRY_TYPE_LABELS[row.entry_type] ?? row.entry_type}
                  </td>
                  <td className="px-3 py-2.5">
                    <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium ${
                      isAmount ? "bg-indigo-50 text-indigo-600" : "bg-blue-50 text-blue-700"
                    }`}>
                      {isAmount ? "Amounts" : "Status"}
                    </span>
                  </td>

                  {/* Q1–Q4 */}
                  {isAmount ? (
                    <>
                      <td className="px-3 py-2.5"><AmountDiff oldVal={row.q1_old} newVal={row.q1_new} /></td>
                      <td className="px-3 py-2.5"><AmountDiff oldVal={row.q2_old} newVal={row.q2_new} /></td>
                      <td className="px-3 py-2.5"><AmountDiff oldVal={row.q3_old} newVal={row.q3_new} /></td>
                      <td className="px-3 py-2.5"><AmountDiff oldVal={row.q4_old} newVal={row.q4_new} /></td>
                    </>
                  ) : (
                    <>
                      <td className="px-3 py-2.5 text-right font-mono text-[11px] tabular-nums text-gray-300">{fmtK(row.current_q1)}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-[11px] tabular-nums text-gray-300">{fmtK(row.current_q2)}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-[11px] tabular-nums text-gray-300">{fmtK(row.current_q3)}</td>
                      <td className="px-3 py-2.5 text-right font-mono text-[11px] tabular-nums text-gray-300">{fmtK(row.current_q4)}</td>
                    </>
                  )}

                  {/* Status */}
                  <td className="px-3 py-2.5">
                    {row.status_old || row.status_new ? (
                      <div className="flex items-center gap-1.5">
                        <StatusBadge value={row.status_old} />
                        <span className="text-gray-300">→</span>
                        <StatusBadge value={row.status_new} />
                      </div>
                    ) : (
                      <StatusBadge value={row.current_status} />
                    )}
                  </td>

                  <td className="px-3 py-2.5 text-gray-400 text-[11px]">{row.changed_by}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Legend */}
      <div className="px-4 py-2.5 border-t border-gray-100 flex items-center gap-4 text-[10px] text-gray-400 flex-wrap">
        <span>Amount rows: <span className="text-gray-400 line-through">strikethrough</span> = old · <span className="text-indigo-700 font-semibold">indigo</span> = new</span>
        <span>Status rows: Q amounts shown as current (greyed)</span>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

const CURRENT_YEAR = new Date().getFullYear();
const AVAILABLE_FYS = [CURRENT_YEAR - 1, CURRENT_YEAR, CURRENT_YEAR + 1, CURRENT_YEAR + 2];

export default function BudgetAuditReportPage() {
  const [fiscalYear,    setFiscalYear]    = useState(CURRENT_YEAR + 1);
  const [selScenarios,  setSelScenarios]  = useState([]);
  const [selDepts,      setSelDepts]      = useState([]);
  const [selEntryTypes, setSelEntryTypes] = useState([]);
  const [selEventTypes, setSelEventTypes] = useState([]);
  const [selUsers,      setSelUsers]      = useState([]);

  const { data: report, isLoading, isError } = useBudgetAuditReport(fiscalYear);

  const filteredRows = useMemo(() => {
    if (!report) return [];
    return report.rows.filter((r) => {
      if (selScenarios.length  && !selScenarios.includes(r.scenario_name))  return false;
      if (selDepts.length      && !selDepts.includes(r.department_name))     return false;
      if (selEntryTypes.length && !selEntryTypes.includes(r.entry_type))     return false;
      if (selEventTypes.length && !selEventTypes.includes(r.event_type))     return false;
      if (selUsers.length      && !selUsers.includes(r.changed_by))          return false;
      return true;
    });
  }, [report, selScenarios, selDepts, selEntryTypes, selEventTypes, selUsers]);

  const kpis = useMemo(() => {
    const total       = filteredRows.length;
    const amtChanges  = filteredRows.filter((r) => r.event_type === "AMOUNT_CHANGED").length;
    const statChanges = filteredRows.filter((r) => r.event_type === "STATUS_CHANGED").length;
    const uniqueUsers = new Set(filteredRows.map((r) => r.changed_by)).size;
    const uniqueDepts = new Set(filteredRows.map((r) => r.department_name)).size;
    return { total, amtChanges, statChanges, uniqueUsers, uniqueDepts };
  }, [filteredRows]);

  const opts = report?.filter_options;

  return (
    <div className="p-6 space-y-5">

      {/* Header */}
      <div className="flex items-start justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-base font-semibold text-gray-900">Budget Change Log</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            Full audit trail — amount edits and status transitions by scenario, department, and user
          </p>
        </div>
        <div className="flex items-center gap-1">
          {AVAILABLE_FYS.map((fy) => (
            <Pill key={fy} active={fiscalYear === fy} onClick={() => setFiscalYear(fy)}>
              FY{fy}
            </Pill>
          ))}
        </div>
      </div>

      {/* Filters */}
      {opts && (
        <div className="bg-white border border-gray-100 rounded-xl px-4 py-3">
          <div className="grid grid-cols-5 gap-3">
            <DropdownSlicer title="Scenario"   options={opts.scenarios}   selected={selScenarios}  onToggle={setSelScenarios}  searchable />
            <DropdownSlicer title="Department" options={opts.departments} selected={selDepts}       onToggle={setSelDepts}       searchable />
            <DropdownSlicer title="Category"   options={opts.entry_types} selected={selEntryTypes} onToggle={setSelEntryTypes} />
            <DropdownSlicer title="Event"      options={opts.event_types} selected={selEventTypes} onToggle={setSelEventTypes} />
            <DropdownSlicer title="Changed By" options={opts.users}       selected={selUsers}       onToggle={setSelUsers}       searchable />
          </div>
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
        <KpiCard label="Total Events"      value={kpis.total}       sub="across all filters" />
        <KpiCard label="Amount Changes"    value={kpis.amtChanges}  accent="text-indigo-700" />
        <KpiCard label="Status Changes"    value={kpis.statChanges} accent="text-blue-700" />
        <KpiCard label="Departments"       value={kpis.uniqueDepts} sub="with activity" />
        <KpiCard label="Users"             value={kpis.uniqueUsers} sub="who made changes" />
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400 animate-pulse">
          Loading audit report…
        </div>
      ) : isError ? (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-red-500">
          Failed to load report.
        </div>
      ) : (
        <AuditTable rows={filteredRows} />
      )}

    </div>
  );
}
