import { useState, useMemo } from "react";
import { useContractAuditReport } from "../../data/contracts";
import DropdownSlicer from "../../components/DropdownSlicer";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtDate(iso) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

const EVENT_COLORS = {
  CREATED: "bg-green-50 text-green-700",
  UPDATED: "bg-indigo-50 text-indigo-700",
  DELETED: "bg-red-50 text-red-600",
};

const ENTITY_COLORS = {
  Contract: "bg-gray-100 text-gray-600",
  Line:     "bg-amber-50 text-amber-700",
};

const FIELD_LABELS = {
  status:           "Status",
  entered_amount:   "Amount",
  period_start:     "Start",
  period_end:       "End",
  billing_interval: "Billing",
  vendor_name:      "Vendor",
  description:      "Description",
  oracle_account_number: "Account #",
  oracle_account_sub_group: "Sub Group",
  oracle_department: "Department",
  purchase_order_number: "PO #",
};

function FieldDiff({ field, old: oldVal, new: newVal }) {
  const label = FIELD_LABELS[field] ?? field;
  const changed = String(oldVal) !== String(newVal);
  return (
    <div className="flex items-start gap-1 text-[11px] leading-tight">
      <span className="text-gray-400 shrink-0 min-w-[60px]">{label}:</span>
      {changed ? (
        <span className="flex items-center gap-1 flex-wrap">
          <span className="text-gray-400 line-through">{oldVal ?? "—"}</span>
          <span className="text-gray-300">→</span>
          <span className="text-indigo-700 font-medium">{newVal ?? "—"}</span>
        </span>
      ) : (
        <span className="text-gray-500">{newVal ?? "—"}</span>
      )}
    </div>
  );
}

function ChangesCell({ event_type, changes }) {
  if (event_type !== "UPDATED" || !changes || Object.keys(changes).length === 0) {
    return <span className="text-gray-300 text-[11px]">—</span>;
  }
  return (
    <div className="space-y-0.5">
      {Object.entries(changes).map(([field, diff]) => (
        <FieldDiff key={field} field={field} old={diff.old} new={diff.new} />
      ))}
    </div>
  );
}

// ── KPI card ──────────────────────────────────────────────────────────────────

function KpiCard({ label, value, accent }) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1.5">{label}</div>
      <div className={`text-xl font-semibold truncate ${accent || "text-gray-900"}`}>{value}</div>
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
              <th className="sticky left-0 z-10 bg-gray-50 px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[160px]">When</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[140px]">Vendor</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[110px]">PO</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[80px]">Entity</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[80px]">Event</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[280px]">Changes</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[140px]">Changed By</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row) => (
              <tr key={row.audit_id} className="hover:bg-gray-50 group">
                <td className="sticky left-0 z-10 bg-white group-hover:bg-gray-50 px-4 py-2.5 whitespace-nowrap text-gray-500">
                  {fmtDate(row.changed_at)}
                </td>
                <td className="px-3 py-2.5 font-medium text-gray-800">{row.vendor_name}</td>
                <td className="px-3 py-2.5 text-gray-500 font-mono">
                  <div>{row.purchase_order_number}</div>
                  {row.po_line_number != null && (
                    <div className="text-gray-400 text-[10px]">Line {row.po_line_number}</div>
                  )}
                </td>
                <td className="px-3 py-2.5">
                  <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium ${ENTITY_COLORS[row.entity_type] ?? "bg-gray-100 text-gray-500"}`}>
                    {row.entity_type}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium ${EVENT_COLORS[row.event_type] ?? "bg-gray-100 text-gray-500"}`}>
                    {row.event_type}
                  </span>
                </td>
                <td className="px-3 py-2.5">
                  <ChangesCell event_type={row.event_type} changes={row.changes} />
                </td>
                <td className="px-3 py-2.5 text-gray-400 text-[11px]">{row.changed_by}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="px-4 py-2.5 border-t border-gray-100 flex items-center gap-4 text-[10px] text-gray-400 flex-wrap">
        <span>Updated rows: <span className="text-gray-400 line-through">strikethrough</span> = old · <span className="text-indigo-700 font-medium">indigo</span> = new</span>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ContractAuditReportPage() {
  const [selVendors,     setSelVendors]     = useState([]);
  const [selEventTypes,  setSelEventTypes]  = useState([]);
  const [selEntityTypes, setSelEntityTypes] = useState([]);
  const [selUsers,       setSelUsers]       = useState([]);

  const { data: report, isLoading, isError } = useContractAuditReport();

  const filteredRows = useMemo(() => {
    if (!report) return [];
    return report.rows.filter((r) => {
      if (selVendors.length     && !selVendors.includes(r.vendor_name))      return false;
      if (selEventTypes.length  && !selEventTypes.includes(r.event_type))    return false;
      if (selEntityTypes.length && !selEntityTypes.includes(r.entity_type))  return false;
      if (selUsers.length       && !selUsers.includes(r.changed_by))         return false;
      return true;
    });
  }, [report, selVendors, selEventTypes, selEntityTypes, selUsers]);

  const kpis = useMemo(() => ({
    total:    filteredRows.length,
    created:  filteredRows.filter((r) => r.event_type === "CREATED").length,
    updated:  filteredRows.filter((r) => r.event_type === "UPDATED").length,
    deleted:  filteredRows.filter((r) => r.event_type === "DELETED").length,
    vendors:  new Set(filteredRows.map((r) => r.vendor_name)).size,
  }), [filteredRows]);

  const opts = report?.filter_options;

  return (
    <div className="p-6 space-y-5">

      {/* Header */}
      <div>
        <h1 className="text-base font-semibold text-gray-900">Contract Change Log</h1>
        <p className="text-xs text-gray-400 mt-0.5">
          Full audit trail — contract and line events across all vendors
        </p>
      </div>

      {/* Filters */}
      {opts && (
        <div className="bg-white border border-gray-100 rounded-xl px-4 py-3">
          <div className="grid grid-cols-4 gap-3">
            <DropdownSlicer title="Vendor"      options={opts.vendors}      selected={selVendors}     onToggle={setSelVendors}     searchable />
            <DropdownSlicer title="Event"       options={opts.event_types}  selected={selEventTypes}  onToggle={setSelEventTypes}  />
            <DropdownSlicer title="Entity"      options={opts.entity_types} selected={selEntityTypes} onToggle={setSelEntityTypes} />
            <DropdownSlicer title="Changed By"  options={opts.users}        selected={selUsers}       onToggle={setSelUsers}       searchable />
          </div>
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-5 gap-3">
        <KpiCard label="Total Events"  value={kpis.total}   />
        <KpiCard label="Created"       value={kpis.created} accent="text-green-700" />
        <KpiCard label="Updated"       value={kpis.updated} accent="text-indigo-700" />
        <KpiCard label="Deleted"       value={kpis.deleted} accent="text-red-600" />
        <KpiCard label="Vendors"       value={kpis.vendors} />
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400 animate-pulse">
          Loading change log…
        </div>
      ) : isError ? (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-red-500">
          Failed to load change log.
        </div>
      ) : (
        <AuditTable rows={filteredRows} />
      )}

    </div>
  );
}
