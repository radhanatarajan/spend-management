import { useState, useMemo, Fragment } from "react";
import { useUpsertEntry, useUpdateEntryStatus } from "../../../data/budget/hooks";
import { useAuth } from "../../../context/AuthContext";

const STATUS_LABELS = {
  DRAFT:            "Draft",
  READY_FOR_REVIEW: "Ready for Review",
  APPROVED:         "Approved",
  FINAL:            "Final",
  CANCELLED:        "Cancelled",
};
const STATUS_COLORS = {
  DRAFT:            "bg-gray-100 text-gray-500",
  READY_FOR_REVIEW: "bg-blue-50 text-blue-700",
  APPROVED:         "bg-green-50 text-green-700",
  FINAL:            "bg-purple-50 text-purple-700",
  CANCELLED:        "bg-red-50 text-red-500",
};
const ALLOWED_TRANSITIONS = {
  DRAFT:            { SERVICE_OWNER: ["READY_FOR_REVIEW","CANCELLED"], BIZ_ADMIN: ["READY_FOR_REVIEW","CANCELLED"], ADMIN: ["READY_FOR_REVIEW","CANCELLED"] },
  READY_FOR_REVIEW: { BIZ_ADMIN: ["DRAFT","APPROVED","CANCELLED"], ADMIN: ["DRAFT","APPROVED","CANCELLED"] },
  APPROVED:         { BIZ_ADMIN: ["READY_FOR_REVIEW","FINAL","CANCELLED"], ADMIN: ["READY_FOR_REVIEW","FINAL","CANCELLED"] },
  FINAL:            { ADMIN: ["APPROVED"] },
  CANCELLED:        { ADMIN: ["DRAFT"] },
};

const fmtFull = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
const fmt = (v) => fmtFull.format(Number(v ?? 0));

const QUARTERS = ["q1", "q2", "q3", "q4"];
const Q_LABELS = { q1: "Q1 (Jan–Mar)", q2: "Q2 (Apr–Jun)", q3: "Q3 (Jul–Sep)", q4: "Q4 (Oct–Dec)" };

function parseAmount(raw) {
  if (raw === "" || raw == null) return null;
  const n = parseFloat(String(raw).replace(/,/g, ""));
  return isNaN(n) ? null : n;
}

function AccountGroupBadges({ groups }) {
  if (!groups?.length) return <span className="text-[10px] text-gray-300">—</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {groups.map((ag) => (
        <span key={ag} className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100 whitespace-nowrap">
          {ag}
        </span>
      ))}
    </div>
  );
}

function EditableRow({ dept, scenarioId, label, rowClass, initialAmounts, entryId, entryType, entryStatus, userRole, isSelected, onToggle }) {
  const upsert = useUpsertEntry();
  const updateStatus = useUpdateEntryStatus();
  const [draft, setDraft] = useState({
    q1: initialAmounts?.q1 ?? null,
    q2: initialAmounts?.q2 ?? null,
    q3: initialAmounts?.q3 ?? null,
    q4: initialAmounts?.q4 ?? null,
  });

  const status = entryStatus ?? "DRAFT";
  const isLocked = status === "FINAL";
  const allowedNext = entryId ? (ALLOWED_TRANSITIONS[status]?.[userRole] ?? []) : [];

  function handleBlur(q, rawValue) {
    const parsed = parseAmount(rawValue);
    const next = { ...draft, [q]: parsed };
    setDraft(next);
    upsert.mutate({
      scenario_id: scenarioId,
      department_name: dept.department_name,
      entry_type: entryType,
      q1_amount: next.q1, q2_amount: next.q2, q3_amount: next.q3, q4_amount: next.q4,
    });
  }

  function handleStatusChange(e) {
    const next = e.target.value;
    if (!next || !entryId) return;
    updateStatus.mutate({ id: entryId, status: next });
  }

  const annual = QUARTERS.reduce((s, q) => s + Number(draft[q] ?? 0), 0);

  return (
    <tr className={rowClass}>
      {/* Checkbox */}
      <td className="px-2 py-2 text-center w-8">
        <input
          type="checkbox"
          disabled={!entryId}
          checked={isSelected}
          onChange={() => entryId && onToggle(entryId)}
          className="w-3.5 h-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-400 disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed"
        />
      </td>
      {/* dept cell omitted — covered by rowSpan from the Current row above */}
      {/* Category */}
      <td className="px-3 py-2 text-xs text-gray-600 whitespace-nowrap">{label}</td>
      {/* Account Group */}
      <td className="px-3 py-2"><AccountGroupBadges groups={dept.account_groups} /></td>
      {/* Quarter inputs */}
      {QUARTERS.map((q) => (
        <td key={q} className="px-2 py-1.5">
          {isLocked ? (
            <div className="text-right text-xs font-mono tabular-nums px-1.5 py-1 text-gray-500">
              {draft[q] != null && Number(draft[q]) !== 0 ? fmt(draft[q]) : "—"}
            </div>
          ) : (
            <input
              type="number" min="0" step="1000"
              defaultValue={draft[q] != null && Number(draft[q]) !== 0 ? Math.round(Number(draft[q])) : ""}
              key={`${entryId ?? "new"}-${q}-${initialAmounts?.[q]}`}
              onBlur={(e) => handleBlur(q, e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && e.currentTarget.blur()}
              placeholder="—"
              className="w-full text-right text-xs font-mono tabular-nums border border-transparent rounded px-1.5 py-1 focus:outline-none focus:border-indigo-300 focus:bg-indigo-50 hover:border-gray-200 bg-transparent text-gray-700 placeholder-gray-300"
            />
          )}
        </td>
      ))}
      {/* FY Total */}
      <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums font-semibold text-gray-900 bg-gray-50/60">
        {fmt(annual)}
      </td>
      {/* Status */}
      <td className="px-3 py-2 whitespace-nowrap">
        <div className="flex items-center gap-1.5">
          <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[status] ?? STATUS_COLORS.DRAFT}`}>
            {STATUS_LABELS[status] ?? status}
          </span>
          {allowedNext.length > 0 && (
            <select value="" onChange={handleStatusChange} disabled={updateStatus.isPending}
              className="text-[10px] border border-gray-200 rounded px-1 py-0.5 text-gray-500 bg-white focus:outline-none disabled:opacity-60">
              <option value="">Move…</option>
              {allowedNext.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
            </select>
          )}
        </div>
      </td>
    </tr>
  );
}

export default function NonControllableTable({ plan, scenarioId }) {
  const { user } = useAuth();
  const userRole = user?.role ?? "";
  const updateStatus = useUpdateEntryStatus();
  const [selected, setSelected] = useState(new Set());
  const [collapsed, setCollapsed] = useState(new Set());

  function toggleDept(name) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      next.has(name) ? next.delete(name) : next.add(name);
      return next;
    });
  }
  function collapseAll() { setCollapsed(new Set((plan?.departments ?? []).map((d) => d.department_name))); }
  function expandAll()   { setCollapsed(new Set()); }

  const entryStatusMap = useMemo(() => {
    const map = new Map();
    plan?.departments?.forEach((d) => {
      if (d.approved_rec_entry_id) map.set(d.approved_rec_entry_id, d.approved_rec_status ?? "DRAFT");
      if (d.additional_ask_entry_id) map.set(d.additional_ask_entry_id, d.additional_ask_status ?? "DRAFT");
    });
    return map;
  }, [plan]);

  const bulkAllowed = useMemo(() => {
    if (selected.size === 0) return [];
    const sets = [...selected].map((id) => {
      const st = entryStatusMap.get(id) ?? "DRAFT";
      return new Set(ALLOWED_TRANSITIONS[st]?.[userRole] ?? []);
    });
    const [first, ...rest] = sets;
    return [...first].filter((s) => rest.every((set) => set.has(s)));
  }, [selected, entryStatusMap, userRole]);

  function toggleRow(id) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  function handleBulkStatus(targetStatus) {
    [...selected].forEach((id) => updateStatus.mutate({ id, status: targetStatus }));
    setSelected(new Set());
  }

  if (!plan) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
        Loading budget data…
      </div>
    );
  }

  const { departments, totals } = plan;

  if (!departments?.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
        No department data found. Select cost elements above to see Current amounts.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      {/* Bulk action bar */}
      {selected.size > 0 && (
        <div className="px-4 py-2.5 bg-indigo-50 border-b border-indigo-100 flex items-center gap-3 flex-wrap">
          <span className="text-xs font-medium text-indigo-700">
            {selected.size} row{selected.size !== 1 ? "s" : ""} selected
          </span>
          {bulkAllowed.length > 0 ? (
            <>
              <span className="text-xs text-indigo-400">Move to:</span>
              <div className="flex gap-1.5 flex-wrap">
                {bulkAllowed.map((s) => (
                  <button key={s} onClick={() => handleBulkStatus(s)} disabled={updateStatus.isPending}
                    className="text-[11px] px-2.5 py-1 rounded border border-indigo-200 bg-white text-indigo-700 hover:bg-indigo-100 disabled:opacity-60 transition-colors">
                    {STATUS_LABELS[s]}
                  </button>
                ))}
              </div>
            </>
          ) : (
            <span className="text-xs text-gray-400 italic">Selected rows have no common valid transition</span>
          )}
          <button onClick={() => setSelected(new Set())} className="ml-auto text-[11px] text-gray-400 hover:text-gray-600">
            Clear selection
          </button>
        </div>
      )}

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
            <tr className="bg-gray-50 border-b-2 border-gray-200">
              <th className="w-8 px-2 py-3 bg-gray-50" />
              <th className="sticky left-0 z-10 bg-gray-50 px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[180px] border-r border-gray-200">
                Department
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[200px]">Category</th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[130px]">Account Group</th>
              {QUARTERS.map((q) => (
                <th key={q} className="px-3 py-3 text-right font-medium text-gray-500 uppercase tracking-wide min-w-[140px]">
                  {Q_LABELS[q]}
                </th>
              ))}
              <th className="px-3 py-3 text-right font-medium text-gray-500 uppercase tracking-wide min-w-[120px] bg-gray-100">
                FY Total
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[160px]">
                Status
              </th>
            </tr>
          </thead>
          <tbody>
            {departments.map((dept, di) => {
              const isCollapsed = collapsed.has(dept.department_name);
              const currentAnnual  = QUARTERS.reduce((s, q) => s + Number(dept.current?.[q]       ?? 0), 0);
              const recAnnual      = QUARTERS.reduce((s, q) => s + Number(dept.approved_rec?.[q]   ?? 0), 0);
              const askAnnual      = QUARTERS.reduce((s, q) => s + Number(dept.additional_ask?.[q] ?? 0), 0);
              const borderTop = di > 0 ? "border-t-2 border-gray-200" : "";

              const deptCell = (rowSpan) => (
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

              if (isCollapsed) {
                return (
                  <Fragment key={dept.department_name}>
                    <tr
                      className={`bg-gray-50/60 hover:bg-gray-100/60 ${borderTop}`}
                      onClick={() => toggleDept(dept.department_name)}
                    >
                      <td className="px-2 py-2.5 w-8" />
                      {deptCell(1)}
                      {/* summary spanning Category + Account Group + Q1-Q4 + FY Total + Status */}
                      <td colSpan={8} className="px-3 py-2.5 text-[11px] text-gray-400 cursor-pointer">
                        <span className="text-emerald-700 font-medium">{fmt(currentAnnual)}</span>
                        <span className="mx-2 text-gray-200">|</span>
                        <span className="text-gray-500">Rec</span>
                        <span className="ml-1 text-indigo-700 font-medium">{fmt(recAnnual)}</span>
                        <span className="mx-2 text-gray-200">|</span>
                        <span className="text-gray-500">Ask</span>
                        <span className="ml-1 text-amber-700 font-medium">{fmt(askAnnual)}</span>
                      </td>
                    </tr>
                  </Fragment>
                );
              }

              return (
                <Fragment key={dept.department_name}>
                  {/* Row 1: Current — dept cell spans all 3 rows */}
                  <tr className={`bg-white ${borderTop}`}>
                    <td className="px-2 py-2.5 w-8" />
                    {deptCell(3)}
                    <td className="px-3 py-2.5 text-xs text-gray-500 whitespace-nowrap">Current (Actuals + Forecast)</td>
                    <td className="px-3 py-2.5"><AccountGroupBadges groups={dept.account_groups} /></td>
                    {QUARTERS.map((q) => (
                      <td key={q} className={`px-3 py-2.5 text-right font-mono text-xs tabular-nums ${
                        dept.current_is_forecast?.[q] ? "text-amber-600 italic" : "text-emerald-700 font-medium"
                      }`}>
                        {fmt(dept.current?.[q])}
                      </td>
                    ))}
                    <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums font-semibold text-gray-900 bg-gray-50/60">
                      {fmt(currentAnnual)}
                    </td>
                    <td className="px-3 py-2.5" />
                  </tr>

                  {/* Row 2: Current Approved Rec */}
                  <EditableRow
                    dept={dept} scenarioId={scenarioId}
                    label="Current Approved Rec"
                    rowClass="bg-white border-t border-gray-100"
                    initialAmounts={dept.approved_rec}
                    entryId={dept.approved_rec_entry_id}
                    entryType="APPROVED_REC"
                    entryStatus={dept.approved_rec_status}
                    userRole={userRole}
                    isSelected={selected.has(dept.approved_rec_entry_id)}
                    onToggle={toggleRow}
                  />

                  {/* Row 3: Additional Ask */}
                  <EditableRow
                    dept={dept} scenarioId={scenarioId}
                    label="Additional Ask"
                    rowClass="bg-amber-50/20 border-t border-gray-100"
                    initialAmounts={dept.additional_ask}
                    entryId={dept.additional_ask_entry_id}
                    entryType="ADDITIONAL_ASK"
                    entryStatus={dept.additional_ask_status}
                    userRole={userRole}
                    isSelected={selected.has(dept.additional_ask_entry_id)}
                    onToggle={toggleRow}
                  />
                </Fragment>
              );
            })}

            {/* Grand Total — 3 rows using same rowspan pattern */}
            <tr className="bg-gray-100 border-t-2 border-gray-300">
              <td className="px-2 py-3 w-8" />
              <td rowSpan={3} className="sticky left-0 z-10 px-4 py-3 bg-gray-100 align-middle border-r border-gray-200">
                <span className="text-xs font-bold text-gray-800 uppercase tracking-wide">Grand Total</span>
              </td>
              <td className="px-3 py-3 text-xs font-bold text-gray-600 uppercase tracking-wide">Current</td>
              <td className="px-3 py-3" />
              {QUARTERS.map((q) => (
                <td key={q} className="px-3 py-3 text-right font-mono text-xs tabular-nums font-bold text-gray-900">
                  {fmt(totals?.current?.[q])}
                </td>
              ))}
              <td className="px-3 py-3 text-right font-mono text-xs tabular-nums font-bold text-gray-900 bg-gray-200/60">
                {fmt(totals?.current?.annual)}
              </td>
              <td className="px-3 py-3" />
            </tr>
            <tr className="bg-gray-100 border-t border-gray-200">
              <td className="px-2 py-2.5" />
              <td className="px-3 py-2.5 text-xs font-bold text-indigo-700 uppercase tracking-wide">Approved Rec</td>
              <td className="px-3 py-2.5" />
              {QUARTERS.map((q) => (
                <td key={q} className="px-3 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-indigo-700">
                  {fmt(totals?.approved_rec?.[q])}
                </td>
              ))}
              <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-indigo-700 bg-gray-200/60">
                {fmt(totals?.approved_rec?.annual)}
              </td>
              <td className="px-3 py-2.5" />
            </tr>
            <tr className="bg-gray-100 border-t border-gray-200">
              <td className="px-2 py-2.5" />
              <td className="px-3 py-2.5 text-xs font-bold text-amber-700 uppercase tracking-wide">Additional Ask</td>
              <td className="px-3 py-2.5" />
              {QUARTERS.map((q) => (
                <td key={q} className="px-3 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-amber-700">
                  {fmt(totals?.additional_ask?.[q])}
                </td>
              ))}
              <td className="px-3 py-2.5 text-right font-mono text-xs tabular-nums font-bold text-amber-700 bg-gray-200/60">
                {fmt(totals?.additional_ask?.annual)}
              </td>
              <td className="px-3 py-2.5" />
            </tr>
          </tbody>
        </table>
      </div>

      <div className="px-4 py-2.5 border-t border-gray-100 flex items-center gap-4 text-[10px] text-gray-400 flex-wrap">
        <span><span className="text-emerald-700 font-medium">Green</span> = confirmed actuals</span>
        <span><span className="text-amber-500 italic">Italic amber</span> = carry-forward forecast</span>
        <span><span className="text-purple-600 font-medium">Final</span> rows are read-only</span>
        <span>Check rows to bulk-update status · Click any editable cell — saves on blur</span>
      </div>
    </div>
  );
}
