import { useState, useMemo, Fragment } from "react";
import { useUpsertControllableEntry, useUpdateControllableEntryStatus, useUpsertLineOverride } from "../../../data/budget/hooks";
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

function deriveExpenseType(activityId, storedExpenseType) {
  if (storedExpenseType) return storedExpenseType === "capex" ? "Capex" : "Opex";
  if (!activityId) return null;
  if (activityId.startsWith("ACAPEX")) return "Capex";
  if (activityId.startsWith("AOPEX")) return "Opex";
  if (activityId.startsWith("NC-")) return "Opex";
  return null;
}
const fmtCompact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });
const fmt  = (v) => fmtFull.format(Number(v ?? 0));
const fmtK = (v) => fmtCompact.format(Number(v ?? 0));

function parseAmount(raw) {
  if (raw === "" || raw == null) return null;
  const n = parseFloat(String(raw).replace(/,/g, ""));
  return isNaN(n) ? null : n;
}

function StatusBadge({ status }) {
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[status] ?? "bg-gray-100 text-gray-400"}`}>
      {STATUS_LABELS[status] ?? status ?? "—"}
    </span>
  );
}

function LineDetailRow({ line, scenarioId }) {
  const upsertOverride = useUpsertLineOverride();
  const [action, setAction] = useState(line.override_action ?? "keep");
  const [savedBriefly, setSavedBriefly] = useState(false);

  // Seed from stored override; fall back to contracted quarterly amounts
  const seedQ = (extended, contracted) => {
    if (extended != null) return String(Math.round(Number(extended)));
    const n = Math.round(Number(contracted));
    return n !== 0 ? String(n) : "";
  };
  const [ext, setExt] = useState({
    q1: seedQ(line.q1_extended, line.q1_contribution),
    q2: seedQ(line.q2_extended, line.q2_contribution),
    q3: seedQ(line.q3_extended, line.q3_contribution),
    q4: seedQ(line.q4_extended, line.q4_contribution),
  });

  // Original contracted amounts for diff display
  const contracted = {
    q1: Math.round(Number(line.q1_contribution)),
    q2: Math.round(Number(line.q2_contribution)),
    q3: Math.round(Number(line.q3_contribution)),
    q4: Math.round(Number(line.q4_contribution)),
  };

  function doSave(newAction, newExt) {
    upsertOverride.mutate({
      scenario_id: scenarioId,
      contract_line_id: line.contract_line_id,
      action: newAction,
      q1_extended: newAction === "extend" ? (parseAmount(newExt.q1) ?? null) : null,
      q2_extended: newAction === "extend" ? (parseAmount(newExt.q2) ?? null) : null,
      q3_extended: newAction === "extend" ? (parseAmount(newExt.q3) ?? null) : null,
      q4_extended: newAction === "extend" ? (parseAmount(newExt.q4) ?? null) : null,
    });
    // Show saved briefly; the hook's onSuccess handles the refetch
    setSavedBriefly(true);
    setTimeout(() => setSavedBriefly(false), 1800);
  }

  function handleActionChange(e) {
    const v = e.target.value;
    setAction(v);
    if (v !== "extend") doSave(v, ext);
  }

  const formatPeriod = (s, e) => {
    const d = (x) => new Date(x + "T00:00:00").toLocaleDateString("en-US", { month: "short", year: "2-digit" });
    return `${d(s)} – ${d(e)}`;
  };

  const actionColor = action === "cancel"
    ? "text-red-600 border-red-200 bg-red-50"
    : action === "extend"
    ? "text-indigo-600 border-indigo-200 bg-indigo-50"
    : "text-gray-500 bg-white border-gray-200";

  // Whether a quarter's entered value differs from the contracted baseline
  const hasDiff = (q) => {
    const entered = parseAmount(ext[q]) ?? 0;
    return entered !== contracted[q];
  };

  const extTotal = ["q1","q2","q3","q4"].reduce((s, q) => s + (parseAmount(ext[q]) ?? 0), 0);

  return (
    <tr className="bg-gray-50 border-b border-gray-100 text-xs text-gray-600">
      <td className="pl-10 py-2 font-medium text-gray-700" colSpan={3}>{line.vendor_name}</td>
      <td className="px-3 py-2">{line.po_number}</td>
      <td className="px-3 py-2 text-center">{line.po_line_number}</td>
      <td className="px-3 py-2 whitespace-nowrap">{formatPeriod(line.period_start, line.period_end)}</td>

      {/* C+F column: FY contribution + action selector */}
      <td className="px-3 py-2">
        <div className="flex items-center justify-end gap-2">
          <span className="tabular-nums text-emerald-700">{fmtK(line.fy_contribution)}</span>
          <select
            value={action}
            onChange={handleActionChange}
            className={`text-[11px] border rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-indigo-300 ${actionColor}`}
          >
            <option value="keep">Keep</option>
            <option value="cancel">Cancel</option>
            <option value="extend">Extend</option>
          </select>
        </div>
      </td>

      {action === "extend" ? (
        <>
          {["q1","q2","q3","q4"].map((q) => {
            const changed = hasDiff(q);
            return (
              <td key={q} className="px-2 py-1.5 text-right">
                <input
                  type="number"
                  value={ext[q]}
                  onChange={(e) => setExt((prev) => ({ ...prev, [q]: e.target.value }))}
                  placeholder="—"
                  className={`w-24 text-right text-xs tabular-nums border rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 bg-white ${
                    changed
                      ? "border-amber-400 focus:ring-amber-400 text-amber-700"
                      : "border-indigo-300 focus:ring-indigo-400 text-gray-700"
                  }`}
                />
                {/* "was $X" annotation when value differs from contracted */}
                {changed && contracted[q] !== 0 && (
                  <div className="text-[10px] text-gray-400 mt-0.5">
                    was {fmtK(contracted[q])}
                  </div>
                )}
              </td>
            );
          })}

          {/* Total */}
          <td className="px-3 py-1.5 text-right tabular-nums font-medium text-indigo-700 align-top pt-2">
            {fmt(extTotal)}
          </td>

          {/* Save button in Status column */}
          <td className="px-3 py-1.5 align-top pt-2">
            {savedBriefly ? (
              <span className="text-[11px] text-green-600 font-medium">Saved ✓</span>
            ) : (
              <button
                onClick={() => doSave(action, ext)}
                disabled={upsertOverride.isPending}
                className="text-[11px] px-2.5 py-1 rounded bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 whitespace-nowrap"
              >
                {upsertOverride.isPending ? "Saving…" : "Save"}
              </button>
            )}
          </td>
        </>
      ) : (
        <>
          <td colSpan={5} />
          <td className="px-3 py-2" />
        </>
      )}
    </tr>
  );
}

function ControllableRow({ row, scenarioId, fiscalYear, onCreateActivityId, expanded, onToggle, isSelected, onSelectToggle }) {
  const { user }    = useAuth();
  const userRole    = user?.role;
  const upsertEntry = useUpsertControllableEntry();
  const updateStatus = useUpdateControllableEntryStatus();

  const isNewRequest = row.entry_category === "NEW_REQUEST";
  const hasLines     = row.lines?.length > 0 || isNewRequest;
  const status       = row.status ?? "DRAFT";
  const isLocked     = status === "FINAL";

  // Editable draft only for NEW_REQUEST rows; EXISTING rows always derive from contracted amounts
  const [draft, setDraft] = useState({
    q1: row.q1_amount != null ? String(row.q1_amount) : "",
    q2: row.q2_amount != null ? String(row.q2_amount) : "",
    q3: row.q3_amount != null ? String(row.q3_amount) : "",
    q4: row.q4_amount != null ? String(row.q4_amount) : "",
  });

  // For status transitions: if no entry exists yet, create it first then transition
  const allowedNext = row.entry_id
    ? (ALLOWED_TRANSITIONS[status]?.[userRole] ?? [])
    : (ALLOWED_TRANSITIONS["DRAFT"]?.[userRole] ?? []);  // no entry = treat as DRAFT for role check

  function handleBlur() {
    if (!isNewRequest) return;
    upsertEntry.mutate({
      scenario_id:    scenarioId,
      fiscal_year:    fiscalYear,
      activity_id:    row.activity_id,
      entry_label:    row.entry_label,
      entry_category: row.entry_category,
      q1_amount: parseAmount(draft.q1),
      q2_amount: parseAmount(draft.q2),
      q3_amount: parseAmount(draft.q3),
      q4_amount: parseAmount(draft.q4),
    });
  }

  function handleStatusChange(e) {
    const next = e.target.value;
    if (!next) return;
    if (row.entry_id) {
      updateStatus.mutate({ id: row.entry_id, status: next });
    } else {
      // No entry yet — create one (status-only, no amounts for EXISTING rows), then transition
      upsertEntry.mutate({
        scenario_id:    scenarioId,
        fiscal_year:    fiscalYear,
        activity_id:    row.activity_id,
        entry_label:    row.entry_label,
        entry_category: row.entry_category,
        q1_amount: null, q2_amount: null, q3_amount: null, q4_amount: null,
      }, {
        onSuccess: (data) => updateStatus.mutate({ id: data.id, status: next }),
      });
    }
  }

  // For EXISTING rows: Q1–Q4 plan = contracted quarterly totals (auto, no independent entry)
  // For NEW_REQUEST: Q1–Q4 = user-entered draft
  const planQ = {
    q1: isNewRequest ? parseAmount(draft.q1) : Number(row.q1_contracted ?? 0),
    q2: isNewRequest ? parseAmount(draft.q2) : Number(row.q2_contracted ?? 0),
    q3: isNewRequest ? parseAmount(draft.q3) : Number(row.q3_contracted ?? 0),
    q4: isNewRequest ? parseAmount(draft.q4) : Number(row.q4_contracted ?? 0),
  };
  const total = planQ.q1 + planQ.q2 + planQ.q3 + planQ.q4;
  const variance = total - (isNewRequest ? 0 : Number(row.current_and_forecast ?? 0));

  return (
    <Fragment>
      <tr className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
        {/* Expand */}
        {/* Checkbox */}
        <td className="px-2 py-2.5 text-center w-8">
          <input
            type="checkbox"
            disabled={!row.entry_id}
            checked={isSelected}
            onChange={() => row.entry_id && onSelectToggle(row.entry_id)}
            className="w-3.5 h-3.5 rounded border-gray-300 text-indigo-600 focus:ring-indigo-400 disabled:opacity-30 cursor-pointer disabled:cursor-not-allowed"
          />
        </td>

        <td className="pl-3 pr-1 py-2.5 w-8">
          {hasLines && (
            <button
              onClick={onToggle}
              className="p-0.5 rounded hover:bg-gray-100 text-gray-400 transition-colors"
            >
              <svg className={`w-3.5 h-3.5 transition-transform ${expanded ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
              </svg>
            </button>
          )}
        </td>

        {/* Activity ID */}
        <td className="px-3 py-2.5 text-sm">
          {row.activity_id
            ? <span className="font-mono text-xs font-medium text-indigo-700">{row.activity_id}</span>
            : <span className="italic text-gray-500 text-xs">New Request: {row.entry_label}</span>
          }
        </td>

        {/* Department */}
        <td className="px-3 py-2.5 text-xs text-gray-600">{row.department_name ?? "—"}</td>

        {/* Account Group */}
        <td className="px-3 py-2.5">
          {row.account_group
            ? <span className="text-[10px] px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600 border border-indigo-100">{row.account_group}</span>
            : <span className="text-[10px] text-gray-300">—</span>
          }
        </td>

        {/* Sub Group */}
        <td className="px-3 py-2.5 text-xs text-gray-500 max-w-[110px] truncate">{row.account_sub_group ?? "—"}</td>

        {/* Expense Type */}
        <td className="px-3 py-2.5">
          {deriveExpenseType(row.activity_id, row.expense_type)
            ? <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${deriveExpenseType(row.activity_id, row.expense_type) === "Capex" ? "bg-amber-50 text-amber-700 border border-amber-100" : "bg-sky-50 text-sky-700 border border-sky-100"}`}>
                {deriveExpenseType(row.activity_id, row.expense_type)}
              </span>
            : <span className="text-[10px] text-gray-300">—</span>
          }
        </td>

        {/* Current+Forecast — single annual total */}
        <td className="px-3 py-2.5 text-right text-sm tabular-nums text-emerald-700 font-medium">
          {isNewRequest
            ? <span className="text-gray-300">—</span>
            : fmt(row.current_and_forecast)
          }
        </td>

        {/* Q1–Q4 Budget Plan */}
        {["q1","q2","q3","q4"].map((q) => (
          <td key={q} className="px-2 py-2.5 text-right">
            {isNewRequest && !isLocked ? (
              <input
                type="number"
                value={draft[q]}
                onChange={(e) => setDraft((prev) => ({ ...prev, [q]: e.target.value }))}
                onBlur={handleBlur}
                placeholder="—"
                className="w-24 text-right text-sm tabular-nums border border-gray-200 rounded px-1.5 py-0.5 focus:outline-none focus:ring-1 focus:ring-indigo-300 bg-white"
              />
            ) : (
              <span className={`text-sm tabular-nums ${isNewRequest ? "text-gray-700" : "text-indigo-700 font-medium"}`}>
                {planQ[q] ? fmt(planQ[q]) : <span className="text-gray-300">—</span>}
              </span>
            )}
          </td>
        ))}

        {/* Total Budget */}
        <td className="px-3 py-2.5 text-right text-sm tabular-nums font-semibold text-indigo-700">
          {fmt(total)}
        </td>

        {/* Variance (Budget − C+F) */}
        <td className="px-3 py-2.5 text-right text-sm tabular-nums font-medium">
          <span className={variance > 0 ? "text-red-600" : variance < 0 ? "text-green-700" : "text-gray-400"}>
            {fmt(variance)}
          </span>
        </td>

        {/* Status */}
        <td className="px-3 py-2.5">
          <div className="flex items-center gap-1.5 flex-wrap">
            <StatusBadge status={status} />
            {allowedNext.length > 0 && (
              <select
                onChange={handleStatusChange}
                value=""
                className="text-[10px] border border-gray-200 rounded px-1 py-0.5 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-300 text-gray-500"
              >
                <option value="">Move…</option>
                {allowedNext.map((s) => <option key={s} value={s}>{STATUS_LABELS[s]}</option>)}
              </select>
            )}
            {isNewRequest && !row.activity_id && status === "FINAL" && (
              <button
                onClick={() => onCreateActivityId(row)}
                className="text-[10px] px-1.5 py-0.5 rounded bg-green-600 text-white hover:bg-green-700 whitespace-nowrap"
              >
                Create Activity ID
              </button>
            )}
          </div>
        </td>
      </tr>

      {/* Expanded detail */}
      {expanded && (
        <>
          {isNewRequest ? (
            <tr className="bg-gray-50 border-b border-gray-100">
              <td colSpan={15} className="pl-12 py-3 text-xs text-gray-400 italic">
                No linked contract — budget entered manually.
              </td>
            </tr>
          ) : (
            <>
              <tr className="bg-gray-100 border-b border-gray-200 text-[10px] uppercase tracking-wide text-gray-400 font-medium">
                <th className="pl-10 py-1.5" colSpan={5}>Vendor</th>
                <th className="px-3 py-1.5">PO #</th>
                <th className="px-3 py-1.5 text-center">Line</th>
                <th className="px-3 py-1.5">Period</th>
                <th className="px-3 py-1.5 text-right">FY Contribution / Action</th>
                <th className="px-2 py-1.5 text-right text-indigo-500">Q1</th>
                <th className="px-2 py-1.5 text-right text-indigo-500">Q2</th>
                <th className="px-2 py-1.5 text-right text-indigo-500">Q3</th>
                <th className="px-2 py-1.5 text-right text-indigo-500">Q4</th>
                <th className="px-3 py-1.5 text-right text-indigo-500">Total</th>
                <th />
              </tr>
              {row.lines.map((line) => (
                <LineDetailRow key={line.contract_line_id} line={line} scenarioId={scenarioId} />
              ))}
              {row.lines.length === 0 && (
                <tr className="bg-gray-50 border-b border-gray-100">
                  <td colSpan={15} className="pl-12 py-2 text-xs text-gray-400 italic">No contract lines found.</td>
                </tr>
              )}
            </>
          )}
        </>
      )}
    </Fragment>
  );
}

function TotalsRow({ rows }) {
  const cfSum = rows.reduce((s, r) => s + Number(r.current_and_forecast ?? 0), 0);

  // Budget Plan Q1–Q4: contracted amounts for EXISTING rows, entry amounts for NEW_REQUEST
  const planSum = (q) => rows.reduce((s, r) => {
    if (r.entry_category === "NEW_REQUEST") return s + Number(r[`${q}_amount`] ?? 0);
    return s + Number(r[`${q}_contracted`] ?? 0);
  }, 0);
  const budget = ["q1","q2","q3","q4"].reduce((s, q) => s + planSum(q), 0);
  const varianceTotal = budget - cfSum;

  return (
    <tr className="bg-indigo-50 border-t-2 border-indigo-200 font-semibold text-sm">
      <td className="px-2 py-2.5 w-8" />
      <td className="pl-3 py-2.5 w-8" />
      <td className="px-3 py-2.5 text-xs text-indigo-700 font-semibold" colSpan={5}>
        Total ({rows.length} {rows.length === 1 ? "row" : "rows"})
      </td>
      <td className="px-3 py-2.5 text-right tabular-nums text-emerald-700">{fmt(cfSum)}</td>
      {["q1","q2","q3","q4"].map((q) => (
        <td key={q} className="px-2 py-2.5 text-right tabular-nums text-indigo-700">{fmt(planSum(q))}</td>
      ))}
      <td className="px-3 py-2.5 text-right tabular-nums text-indigo-700">{fmt(budget)}</td>
      <td className="px-3 py-2.5 text-right tabular-nums font-semibold">
        <span className={varianceTotal > 0 ? "text-red-600" : varianceTotal < 0 ? "text-green-700" : "text-gray-400"}>
          {fmt(varianceTotal)}
        </span>
      </td>
      <td className="px-3 py-2.5" />
    </tr>
  );
}

export default function ControllableTable({ rows, scenarioId, fiscalYear, onCreateActivityId }) {
  const { user } = useAuth();
  const userRole = user?.role ?? "";
  const updateStatus = useUpdateControllableEntryStatus();

  const [expandedSet, setExpandedSet] = useState(new Set());
  const [selected, setSelected] = useState(new Set());

  const entryStatusMap = useMemo(() => {
    const map = new Map();
    rows.forEach((r) => { if (r.entry_id) map.set(r.entry_id, r.status ?? "DRAFT"); });
    return map;
  }, [rows]);

  const bulkAllowed = useMemo(() => {
    if (selected.size === 0) return [];
    const sets = [...selected].map((id) => {
      const st = entryStatusMap.get(id) ?? "DRAFT";
      return new Set(ALLOWED_TRANSITIONS[st]?.[userRole] ?? []);
    });
    const [first, ...rest] = sets;
    if (!first) return [];
    return [...first].filter((s) => rest.every((set) => set.has(s)));
  }, [selected, entryStatusMap, userRole]);

  function toggleSelect(entryId) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(entryId) ? next.delete(entryId) : next.add(entryId);
      return next;
    });
  }

  function handleBulkStatus(targetStatus) {
    [...selected].forEach((id) => updateStatus.mutate({ id, status: targetStatus }));
    setSelected(new Set());
  }

  const expandableKeys = rows
    .map((r, i) => ({ key: r.activity_id ?? `new-${i}`, hasLines: r.lines?.length > 0 || r.entry_category === "NEW_REQUEST" }))
    .filter((r) => r.hasLines)
    .map((r) => r.key);

  function expandAll()   { setExpandedSet(new Set(expandableKeys)); }
  function collapseAll() { setExpandedSet(new Set()); }
  function toggleRow(key) {
    setExpandedSet((prev) => {
      const next = new Set(prev);
      next.has(key) ? next.delete(key) : next.add(key);
      return next;
    });
  }

  if (!rows?.length) {
    return (
      <div className="text-center py-12 text-sm text-gray-400">
        No controllable budget rows found for this scenario.
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-gray-200 bg-white">
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
        <span className="text-[11px] text-gray-400 mr-1">Rows:</span>
        <button
          onClick={expandAll}
          disabled={expandedSet.size === expandableKeys.length}
          className="flex items-center gap-1 text-[11px] px-2 py-1 rounded border border-gray-200 text-gray-600 hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          Expand All
        </button>
        <button
          onClick={collapseAll}
          disabled={expandedSet.size === 0}
          className="flex items-center gap-1 text-[11px] px-2 py-1 rounded border border-gray-200 text-gray-600 hover:border-indigo-300 hover:text-indigo-700 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
        >
          <svg className="w-3 h-3 rotate-180" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
          Collapse All
        </button>
      </div>

      <div className="overflow-x-auto">
        <table className="min-w-full text-left border-collapse">
          <thead className="bg-gray-50 border-b border-gray-200">
            {/* Group header */}
            <tr className="text-[10px] uppercase tracking-wide font-medium border-b border-gray-100">
              <th className="pl-3 pr-1 py-1.5 w-8" colSpan={7} />
              <th className="px-3 py-1.5 text-center text-emerald-600 bg-emerald-50/60 border-x border-emerald-100" colSpan={1}>
                Current+Forecast
              </th>
              <th className="px-2 py-1.5 text-center text-indigo-600 bg-indigo-50/60" colSpan={5}>
                Budget Plan
              </th>
              <th className="px-3 py-1.5 text-center text-gray-400" colSpan={1}>
                Variance
              </th>
              <th className="px-3 py-1.5" />
            </tr>
            {/* Column labels */}
            <tr className="text-[10px] uppercase tracking-wide text-gray-400 font-medium">
              <th className="px-2 py-2.5 w-8" />
              <th className="pl-3 pr-1 py-2.5 w-8" />
              <th className="px-3 py-2.5">Activity ID</th>
              <th className="px-3 py-2.5">Department</th>
              <th className="px-3 py-2.5">Acct Group</th>
              <th className="px-3 py-2.5">Sub Group</th>
              <th className="px-3 py-2.5">Exp Type</th>
              <th className="px-3 py-2.5 text-right text-emerald-600">Total</th>
              <th className="px-2 py-2.5 text-right text-indigo-600">Q1</th>
              <th className="px-2 py-2.5 text-right text-indigo-600">Q2</th>
              <th className="px-2 py-2.5 text-right text-indigo-600">Q3</th>
              <th className="px-2 py-2.5 text-right text-indigo-600">Q4</th>
              <th className="px-3 py-2.5 text-right text-indigo-600">Total</th>
              <th className="px-3 py-2.5 text-right text-gray-400">Variance</th>
              <th className="px-3 py-2.5">Status</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, i) => {
              const rowKey = row.activity_id ?? `new-${i}`;
              return (
                <ControllableRow
                  key={rowKey}
                  row={row}
                  scenarioId={scenarioId}
                  fiscalYear={fiscalYear}
                  onCreateActivityId={onCreateActivityId}
                  expanded={expandedSet.has(rowKey)}
                  onToggle={() => toggleRow(rowKey)}
                  isSelected={row.entry_id ? selected.has(row.entry_id) : false}
                  onSelectToggle={toggleSelect}
                />
              );
            })}
            <TotalsRow rows={rows} />
          </tbody>
        </table>
      </div>
    </div>
  );
}
