import { useState } from "react";
import { useScenarioAudit } from "../../../data/budget/hooks";

const ENTRY_TYPE_LABELS = {
  APPROVED_REC:   "Approved Rec",
  ADDITIONAL_ASK: "Additional Ask",
};

const STATUS_COLORS = {
  DRAFT:            "bg-gray-100 text-gray-600",
  READY_FOR_REVIEW: "bg-blue-50 text-blue-700",
  APPROVED:         "bg-green-50 text-green-700",
  FINAL:            "bg-purple-50 text-purple-700",
  CANCELLED:        "bg-red-50 text-red-500",
};

const fmtCurrency = new Intl.NumberFormat("en-US", {
  style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0,
});

function fmtAmount(val) {
  if (val == null || val === "None") return "—";
  const n = parseFloat(val);
  return isNaN(n) ? val : fmtCurrency.format(n);
}

function fmtDate(iso) {
  return new Date(iso).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit",
  });
}

function StatusBadge({ value }) {
  return (
    <span className={`inline-block text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[value] ?? "bg-gray-100 text-gray-600"}`}>
      {value}
    </span>
  );
}

const Q_LABEL = { q1_amount: "Q1", q2_amount: "Q2", q3_amount: "Q3", q4_amount: "Q4" };

function ChangeDetail({ event_type, changes }) {
  if (event_type === "STATUS_CHANGED") {
    const { old: oldS, new: newS } = changes.status ?? {};
    return (
      <div className="flex items-center gap-1.5 flex-wrap">
        <StatusBadge value={oldS} />
        <span className="text-gray-400">→</span>
        <StatusBadge value={newS} />
      </div>
    );
  }

  // AMOUNT_CHANGED
  return (
    <div className="space-y-0.5">
      {Object.entries(changes).map(([field, { old: oldV, new: newV }]) => (
        <div key={field} className="flex items-center gap-1.5 text-[11px]">
          <span className="text-gray-400 w-5">{Q_LABEL[field] ?? field}</span>
          <span className="text-gray-400 line-through">{fmtAmount(oldV)}</span>
          <span className="text-gray-400">→</span>
          <span className="text-gray-700 font-medium">{fmtAmount(newV)}</span>
        </div>
      ))}
    </div>
  );
}

function AuditRow({ row }) {
  const isStatus = row.event_type === "STATUS_CHANGED";
  return (
    <div className="flex gap-3 py-3 border-b border-gray-100 last:border-0">
      {/* Timeline dot */}
      <div className="flex flex-col items-center pt-0.5">
        <div className={`w-2 h-2 rounded-full mt-1 shrink-0 ${isStatus ? "bg-blue-400" : "bg-indigo-300"}`} />
        <div className="w-px flex-1 bg-gray-100 mt-1" />
      </div>

      <div className="flex-1 min-w-0 space-y-1">
        {/* Header row */}
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-xs font-medium text-gray-800">{row.department_name}</span>
          <span className="text-[10px] text-gray-400">
            {ENTRY_TYPE_LABELS[row.entry_type] ?? row.entry_type}
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${isStatus ? "bg-blue-50 text-blue-700" : "bg-indigo-50 text-indigo-600"}`}>
            {isStatus ? "Status changed" : "Amounts updated"}
          </span>
        </div>

        {/* Change detail */}
        <ChangeDetail event_type={row.event_type} changes={row.changes} />

        {/* Footer */}
        <div className="text-[10px] text-gray-400">
          {row.changed_by} · {fmtDate(row.changed_at)}
        </div>
      </div>
    </div>
  );
}

export default function AuditLogPanel({ scenarioId }) {
  const [open, setOpen] = useState(false);
  const { data: rows, isLoading } = useScenarioAudit(open ? scenarioId : null);

  const count = rows?.length ?? 0;

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
      {/* Header toggle */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5}
              d="M12 6v6l4 2M12 2a10 10 0 100 20A10 10 0 0012 2z" />
          </svg>
          <span>Audit Log</span>
          {open && !isLoading && count > 0 && (
            <span className="text-[10px] bg-gray-100 text-gray-500 px-1.5 py-0.5 rounded font-normal">
              {count} event{count !== 1 ? "s" : ""}
            </span>
          )}
        </div>
        <svg
          className={`w-4 h-4 text-gray-400 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-4 max-h-96 overflow-y-auto">
          {isLoading && (
            <div className="py-6 text-center text-xs text-gray-400">Loading audit log…</div>
          )}
          {!isLoading && rows?.length === 0 && (
            <div className="py-6 text-center text-xs text-gray-400">No changes recorded yet.</div>
          )}
          {!isLoading && rows?.length > 0 && (
            <div>
              {rows.map((row) => (
                <AuditRow key={row.id} row={row} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
