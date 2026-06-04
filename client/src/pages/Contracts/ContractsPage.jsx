import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import DropdownSlicer from "../../components/DropdownSlicer";
import {
  useContracts,
  useCreateContract,
  useUpdateContract,
  useDeleteContract,
  useAddContractLine,
  useUpdateContractLine,
  useDeleteContractLine,
} from "../../data/contracts";
import { useAccounts, useActivities } from "../../data/reference";

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmt = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 2 });
const fmtUSD = (v) => fmt.format(Number(v));

function fmtPeriod(start, end) {
  const f = (d) => {
    const [y, m] = d.split("-");
    return new Date(Number(y), Number(m) - 1).toLocaleDateString("en-US", { month: "short", year: "2-digit" });
  };
  return `${f(start)} – ${f(end)}`;
}

const STATUS_COLORS = {
  active:    "bg-green-100 text-green-800",
  expired:   "bg-gray-100 text-gray-500",
  cancelled: "bg-red-100 text-red-700",
  pending:   "bg-yellow-100 text-yellow-800",
};

const INTERVAL_OPTIONS = [
  { value: "monthly",   label: "Monthly" },
  { value: "quarterly", label: "Quarterly" },
  { value: "yearly",    label: "Annual" },
  { value: "custom",    label: "Custom (total)" },
];

const INTERVAL_AMOUNT_LABEL = {
  monthly:   "Monthly Amount",
  quarterly: "Quarterly Amount",
  yearly:    "Annual Amount",
  custom:    "Total Amount (period)",
};

function calcMonthlyPreview(entered, interval, periodStart, periodEnd) {
  const v = parseFloat(entered);
  if (isNaN(v) || v <= 0 || !periodStart || !periodEnd) return null;
  if (interval === "monthly") return v;
  if (interval === "quarterly") return v / 3;
  if (interval === "yearly") return v / 12;
  if (interval === "custom") {
    const s = new Date(periodStart), e = new Date(periodEnd);
    const months = (e.getFullYear() - s.getFullYear()) * 12 + e.getMonth() - s.getMonth() + 1;
    return months > 0 ? v / months : null;
  }
  return v;
}

function isMultiYear(lines) {
  const sorted = [...lines].sort((a, b) => a.period_start.localeCompare(b.period_start));
  if (sorted.length < 2) return false;
  for (let i = 0; i < sorted.length - 1; i++) {
    const [ay, am] = sorted[i].period_end.split("-").map(Number);
    const nm = am === 12 ? 1 : am + 1;
    const ny = am === 12 ? ay + 1 : ay;
    const [by, bm] = sorted[i + 1].period_start.split("-").map(Number);
    if (by !== ny || bm !== nm) return false;
  }
  return true;
}

// ── buildPoGroups ─────────────────────────────────────────────────────────────

function buildPoGroups(contracts) {
  return contracts.map((c) => ({
    id: c.id,
    vendor_name: c.vendor_name,
    oracle_department: c.oracle_department,
    oracle_department_name: c.oracle_department_name,
    purchase_order_number: c.purchase_order_number,
    description: c.description,
    status: c.status,
    contract_total: Number(c.contract_total),
    is_multi_year: isMultiYear(c.lines),
    lines: [...c.lines]
      .sort((a, b) => a.period_start.localeCompare(b.period_start))
      .map((l) => ({ ...l, contract_id: c.id })),
  }));
}

// ── StatusBadge ───────────────────────────────────────────────────────────────

function StatusBadge({ status }) {
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium capitalize ${STATUS_COLORS[status] ?? "bg-gray-100 text-gray-600"}`}>
      {status}
    </span>
  );
}

function IntervalBadge({ interval }) {
  const colors = { monthly: "text-blue-600", quarterly: "text-violet-600", yearly: "text-emerald-600", custom: "text-orange-600" };
  const labels = { monthly: "mo", quarterly: "qtr", yearly: "yr", custom: "total" };
  return (
    <span className={`text-xs font-medium uppercase tracking-wide ${colors[interval] ?? "text-gray-500"}`}>
      {labels[interval] ?? interval}
    </span>
  );
}

// ── AccountActivityFields ─────────────────────────────────────────────────────

const inputCls = "w-full border rounded px-2 py-1.5 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500";

function AccountActivityFields({ form, setField, deptCode }) {
  const { data: allAccounts = [] } = useAccounts();
  const { data: allActivities = [] } = useActivities(
    deptCode ? { department_code: deptCode } : undefined
  );

  // Derive cascade from the current account number — no useEffect needed
  const derivedCascade = useMemo(() => {
    if (!form.oracle_account_number || !allAccounts.length) return null;
    const acct = allAccounts.find((a) => a.account_number === form.oracle_account_number);
    if (!acct) return null;
    return { costElement: acct.cost_element ?? "", accountGroup: acct.account_group ?? "", accountSubGroup: acct.account_sub_group ?? "" };
  }, [form.oracle_account_number, allAccounts]);

  // User's explicit cascade selections (null = use derived)
  const [explicitCascade, setExplicitCascade] = useState(null);

  const selCostElement     = explicitCascade?.costElement     ?? derivedCascade?.costElement     ?? "";
  const selAccountGroup    = explicitCascade?.accountGroup    ?? derivedCascade?.accountGroup    ?? "";
  const selAccountSubGroup = explicitCascade?.accountSubGroup ?? derivedCascade?.accountSubGroup ?? "";

  const availableCostElements = useMemo(
    () => [...new Set(allAccounts.map((a) => a.cost_element).filter(Boolean))].sort(),
    [allAccounts]
  );

  const availableAccountGroups = useMemo(
    () =>
      [...new Set(
        allAccounts
          .filter((a) => !selCostElement || a.cost_element === selCostElement)
          .map((a) => a.account_group)
          .filter(Boolean)
      )].sort(),
    [allAccounts, selCostElement]
  );

  const availableSubGroups = useMemo(
    () =>
      [...new Set(
        allAccounts
          .filter(
            (a) =>
              (!selCostElement || a.cost_element === selCostElement) &&
              (!selAccountGroup || a.account_group === selAccountGroup)
          )
          .map((a) => a.account_sub_group)
          .filter(Boolean)
      )].sort(),
    [allAccounts, selCostElement, selAccountGroup]
  );

  const availableAccounts = useMemo(
    () =>
      allAccounts.filter(
        (a) =>
          (!selCostElement || a.cost_element === selCostElement) &&
          (!selAccountGroup || a.account_group === selAccountGroup) &&
          (!selAccountSubGroup || a.account_sub_group === selAccountSubGroup)
      ),
    [allAccounts, selCostElement, selAccountGroup, selAccountSubGroup]
  );

  function handleCostElementChange(v) {
    setExplicitCascade({ costElement: v, accountGroup: "", accountSubGroup: "" });
    setField("oracle_account_number", "");
    setField("oracle_account_sub_group", "");
    setField("activity_id", null);
  }

  function handleAccountGroupChange(v) {
    setExplicitCascade((prev) => ({ ...prev, accountGroup: v, accountSubGroup: "" }));
    setField("oracle_account_number", "");
    setField("oracle_account_sub_group", "");
    setField("activity_id", null);
  }

  function handleSubGroupChange(v) {
    setExplicitCascade((prev) => ({ ...prev, accountSubGroup: v }));
    setField("oracle_account_number", "");
    setField("oracle_account_sub_group", "");
    setField("activity_id", null);
  }

  function handleAccountChange(v) {
    const acct = allAccounts.find((a) => a.account_number === v);
    setField("oracle_account_number", v);
    setField("oracle_account_sub_group", acct?.account_sub_group ?? "");
    setField("activity_id", null);
    setExplicitCascade(null); // let derived cascade reflect the newly selected account
  }

  const selectedAcct = allAccounts.find((a) => a.account_number === form.oracle_account_number);
  const matchingActivities = allActivities.filter(
    (a) => !selectedAcct || a.account_id === selectedAcct.id
  );
  const showCreateLink = deptCode && form.oracle_account_number && matchingActivities.length === 0;

  return (
    <>
      <div>
        <label className="block text-xs text-gray-500 mb-0.5">Cost Element</label>
        <select value={selCostElement} onChange={(e) => handleCostElementChange(e.target.value)} className={inputCls}>
          <option value="">— All —</option>
          {availableCostElements.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-0.5">Account Group</label>
        <select value={selAccountGroup} onChange={(e) => handleAccountGroupChange(e.target.value)} className={inputCls}>
          <option value="">— All —</option>
          {availableAccountGroups.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-0.5">Account Sub-Group</label>
        <select value={selAccountSubGroup} onChange={(e) => handleSubGroupChange(e.target.value)} className={inputCls}>
          <option value="">— All —</option>
          {availableSubGroups.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-xs text-gray-500 mb-0.5">Account Number *</label>
        <select required value={form.oracle_account_number ?? ""} onChange={(e) => handleAccountChange(e.target.value)} className={inputCls}>
          <option value="">— Select —</option>
          {availableAccounts.map((a) => (
            <option key={a.account_number} value={a.account_number}>
              {a.account_number}{a.account_desc ? ` — ${a.account_desc.slice(0, 50)}` : ""}
            </option>
          ))}
        </select>
      </div>
      <div className="col-span-2">
        <label className="block text-xs text-gray-500 mb-0.5">Activity ID</label>
        {matchingActivities.length > 0 ? (
          <select value={form.activity_id ?? ""} onChange={(e) => setField("activity_id", e.target.value || null)} className={inputCls}>
            <option value="">— None —</option>
            {matchingActivities.map((a) => (
              <option key={a.activity_id} value={a.activity_id}>
                {a.activity_id}{a.activity_id_desc ? ` — ${a.activity_id_desc}` : ""}
              </option>
            ))}
          </select>
        ) : showCreateLink ? (
          <div className="flex items-center gap-2 py-1.5 text-xs text-gray-400">
            No activity IDs for this dept + account.
            <Link to="/reference/activities" className="text-blue-600 hover:underline whitespace-nowrap">Create one →</Link>
          </div>
        ) : (
          <select disabled className={`${inputCls} opacity-40`}><option>— Select account first —</option></select>
        )}
      </div>
    </>
  );
}

// ── PoGroupRow ────────────────────────────────────────────────────────────────

function PoGroupRow({ group, collapsed, onToggle, onEditContract, onDeleteContract, onAddLine, onEditLine, onDeleteLine }) {
  if (collapsed || group.lines.length === 0) {
    return (
      <tr className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer" onClick={group.lines.length > 0 ? onToggle : undefined}>
        <td className="w-6 pl-3 py-3 text-gray-300 select-none">
          <svg className="w-3 h-3" viewBox="0 0 12 12" fill="none">
            <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </td>
        <td className="px-3 py-3 min-w-[160px]">
          <div className="font-medium text-gray-900 text-sm flex items-center gap-2">
            {group.vendor_name}
            {group.is_multi_year && (
              <span className="px-1.5 py-0.5 bg-blue-50 text-blue-600 text-xs rounded border border-blue-200">Multi-year</span>
            )}
          </div>
        </td>
        <td className="px-3 py-3 text-xs text-gray-500 min-w-[140px]">{group.oracle_department_name}</td>
        <td className="px-3 py-3 font-mono text-xs text-gray-400 min-w-[130px]">{group.purchase_order_number}</td>
        <td className="px-3 py-3 text-xs text-gray-400" colSpan={6}>
          {group.lines.length === 0
            ? "No lines"
            : `${group.lines.length} line${group.lines.length > 1 ? "s" : ""}`}
          {group.description && <span className="ml-2 text-gray-300">· {group.description.slice(0, 60)}</span>}
        </td>
        <td className="px-3 py-3 text-right font-mono text-sm text-gray-700">{fmtUSD(group.contract_total)}</td>
        <td className="px-3 py-3">
          <div className="flex items-center gap-2 flex-wrap">
            <StatusBadge status={group.status} />
            <div className="flex gap-1 ml-1">
              <button onClick={(e) => { e.stopPropagation(); onEditContract(); }}
                className="text-xs text-blue-400 hover:text-blue-600 px-1.5 py-0.5 border border-blue-200 rounded">
                Edit
              </button>
              <button onClick={(e) => { e.stopPropagation(); onDeleteContract(); }}
                className="text-xs text-red-300 hover:text-red-500 px-1.5 py-0.5 border border-red-100 rounded">
                Del
              </button>
            </div>
          </div>
        </td>
      </tr>
    );
  }

  const rowSpan = group.lines.length;
  return (
    <>
      {group.lines.map((line, idx) => (
        <tr key={line.id} className="border-t border-gray-100 hover:bg-blue-50/20">
          {idx === 0 && (
            <>
              <td
                rowSpan={rowSpan}
                className="w-6 pl-3 align-top pt-3 text-blue-400 cursor-pointer select-none"
                onClick={(e) => { e.stopPropagation(); onToggle(); }}
              >
                <svg className="w-3 h-3 rotate-90" viewBox="0 0 12 12" fill="none">
                  <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </td>
              <td rowSpan={rowSpan} className="px-3 py-3 align-top border-r border-gray-100 min-w-[160px]">
                <div className="font-medium text-gray-900 text-sm flex items-center gap-1.5 flex-wrap">
                  {group.vendor_name}
                  {group.is_multi_year && (
                    <span className="px-1 py-0.5 bg-blue-50 text-blue-600 text-xs rounded border border-blue-100">Multi-year</span>
                  )}
                </div>
                <div className="mt-2 flex flex-col gap-1">
                  <StatusBadge status={group.status} />
                  <div className="text-xs font-mono font-medium text-gray-700">{fmtUSD(group.contract_total)}</div>
                </div>
                <div className="mt-2 flex gap-1 flex-wrap">
                  <button onClick={() => onAddLine()}
                    className="text-xs text-green-600 hover:text-green-700 px-1.5 py-0.5 border border-green-200 rounded">
                    + Line
                  </button>
                  <button onClick={() => onEditContract()}
                    className="text-xs text-blue-400 hover:text-blue-600 px-1.5 py-0.5 border border-blue-200 rounded">
                    Edit PO
                  </button>
                  <button onClick={() => onDeleteContract()}
                    className="text-xs text-red-300 hover:text-red-500 px-1.5 py-0.5 border border-red-100 rounded">
                    Del PO
                  </button>
                </div>
              </td>
              <td rowSpan={rowSpan} className="px-3 py-3 align-top text-xs text-gray-500 min-w-[140px]">
                {group.oracle_department_name}
              </td>
              <td rowSpan={rowSpan} className="px-3 py-3 align-top font-mono text-xs text-gray-400 min-w-[130px]">
                {group.purchase_order_number}
              </td>
            </>
          )}
          <td className="px-3 py-2.5 font-mono text-xs text-gray-500">{line.po_line_number}</td>
          <td className="px-3 py-2.5 font-mono text-xs text-gray-700">{line.oracle_account_number}</td>
          <td className="px-3 py-2.5 font-mono text-xs">
            {line.activity_id
              ? <span className="text-gray-400">{line.activity_id}</span>
              : <span className="text-amber-500 italic">(Unassigned)</span>}
          </td>
          <td className="px-3 py-2.5 text-xs text-gray-600 whitespace-nowrap">{fmtPeriod(line.period_start, line.period_end)}</td>
          <td className="px-3 py-2.5 text-xs text-gray-400 text-center">{line.months_in_period}</td>
          <td className="px-3 py-2.5"><IntervalBadge interval={line.billing_interval} /></td>
          <td className="px-3 py-2.5 text-right font-mono text-xs text-gray-600">{fmtUSD(line.monthly_amount)}</td>
          <td className="px-3 py-2.5 text-right font-mono text-xs font-medium text-gray-800">{fmtUSD(line.total_amount)}</td>
          <td className="px-3 py-2.5">
            <div className="flex items-center gap-2">
              <button onClick={() => onEditLine(line)} className="text-xs text-blue-400 hover:text-blue-600">Edit</button>
              <button onClick={() => onDeleteLine(line)} className="text-xs text-red-300 hover:text-red-500">✕</button>
            </div>
          </td>
        </tr>
      ))}
    </>
  );
}

// ── EditContractModal (header fields only) ────────────────────────────────────

function EditContractModal({ group, onClose }) {
  const [form, setForm] = useState({
    vendor_name: group.vendor_name,
    description: group.description ?? "",
    oracle_department: group.oracle_department,
    oracle_department_name: group.oracle_department_name,
    purchase_order_number: group.purchase_order_number,
    status: group.status,
  });
  const mutation = useUpdateContract();

  function setField(k, v) { setForm((p) => ({ ...p, [k]: v })); }

  function submit(e) {
    e.preventDefault();
    mutation.mutate({ id: group.id, ...form }, { onSuccess: onClose });
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 py-8 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 mx-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Edit Contract</h2>
        <form onSubmit={submit} className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-0.5">Vendor Name *</label>
              <input required value={form.vendor_name} onChange={(e) => setField("vendor_name", e.target.value)}
                className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Department Code *</label>
              <input required value={form.oracle_department} onChange={(e) => setField("oracle_department", e.target.value)}
                className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Department Name *</label>
              <input required value={form.oracle_department_name} onChange={(e) => setField("oracle_department_name", e.target.value)}
                className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">PO Number *</label>
              <input required value={form.purchase_order_number} onChange={(e) => setField("purchase_order_number", e.target.value)}
                className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Status</label>
              <select value={form.status} onChange={(e) => setField("status", e.target.value)} className={inputCls}>
                <option value="active">Active</option>
                <option value="pending">Pending</option>
                <option value="expired">Expired</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-0.5">Description</label>
              <textarea rows={2} value={form.description} onChange={(e) => setField("description", e.target.value)}
                className={`${inputCls} resize-none`} />
            </div>
          </div>
          {mutation.isError && <p className="text-xs text-red-600">Failed to save. Please try again.</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-1.5 border rounded text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={mutation.isPending}
              className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {mutation.isPending ? "Saving…" : "Save Changes"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── LineModal (add or edit a single PO line) ──────────────────────────────────

function LineModal({ mode, contractId, deptCode, line, onClose }) {
  const empty = {
    po_line_number: "",
    oracle_account_number: "",
    oracle_account_sub_group: "",
    activity_id: null,
    period_start: "",
    period_end: "",
    billing_interval: "monthly",
    entered_amount: "",
    notes: "",
  };

  const [form, setForm] = useState(
    mode === "edit" && line
      ? {
          po_line_number: String(line.po_line_number),
          oracle_account_number: line.oracle_account_number,
          oracle_account_sub_group: line.oracle_account_sub_group,
          activity_id: line.activity_id ?? null,
          period_start: line.period_start,
          period_end: line.period_end,
          billing_interval: line.billing_interval,
          entered_amount: String(line.entered_amount),
          notes: line.notes ?? "",
        }
      : empty
  );

  const addMutation    = useAddContractLine();
  const updateMutation = useUpdateContractLine();
  const mutation       = mode === "edit" ? updateMutation : addMutation;

  function setField(k, v) { setForm((p) => ({ ...p, [k]: v })); }

  const monthlyPreview = calcMonthlyPreview(form.entered_amount, form.billing_interval, form.period_start, form.period_end);

  function submit(e) {
    e.preventDefault();
    const payload = {
      po_line_number: Number(form.po_line_number),
      oracle_account_number: form.oracle_account_number,
      oracle_account_sub_group: form.oracle_account_sub_group,
      activity_id: form.activity_id || null,
      period_start: form.period_start,
      period_end: form.period_end,
      billing_interval: form.billing_interval,
      entered_amount: parseFloat(form.entered_amount),
      notes: form.notes || null,
    };
    if (mode === "edit") {
      mutation.mutate({ contractId, lineId: line.id, ...payload }, { onSuccess: onClose });
    } else {
      mutation.mutate({ contractId, ...payload }, { onSuccess: onClose });
    }
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 py-8 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 mx-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {mode === "edit" ? "Edit Line" : "Add Line"}
        </h2>
        <form onSubmit={submit} className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">PO Line # *</label>
              <input required type="number" min="1" value={form.po_line_number}
                onChange={(e) => setField("po_line_number", e.target.value)} className={inputCls} />
            </div>
            <div />

            <AccountActivityFields form={form} setField={setField} deptCode={deptCode} />

            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Service Start *</label>
              <input required type="date" value={form.period_start}
                onChange={(e) => setField("period_start", e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Service End *</label>
              <input required type="date" value={form.period_end}
                onChange={(e) => setField("period_end", e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Billing Interval</label>
              <select value={form.billing_interval} onChange={(e) => setField("billing_interval", e.target.value)} className={inputCls}>
                {INTERVAL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">{INTERVAL_AMOUNT_LABEL[form.billing_interval]} *</label>
              <input required type="number" min="0" step="0.01" value={form.entered_amount}
                onChange={(e) => setField("entered_amount", e.target.value)} className={inputCls} />
              {form.billing_interval !== "monthly" && monthlyPreview != null && (
                <div className="text-xs text-gray-400 mt-0.5">{fmtUSD(monthlyPreview)}/mo</div>
              )}
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-0.5">Notes</label>
              <textarea rows={2} value={form.notes} onChange={(e) => setField("notes", e.target.value)}
                className={`${inputCls} resize-none`} />
            </div>
          </div>
          {mutation.isError && <p className="text-xs text-red-600">Failed to save. Please try again.</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-1.5 border rounded text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={mutation.isPending}
              className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {mutation.isPending ? "Saving…" : mode === "edit" ? "Save Changes" : "Add Line"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── AddContractModal ──────────────────────────────────────────────────────────

const EMPTY_LINE = {
  po_line_number: "",
  oracle_account_number: "",
  oracle_account_sub_group: "",
  activity_id: null,
  period_start: "",
  period_end: "",
  billing_interval: "monthly",
  entered_amount: "",
  notes: "",
};

function AddContractModal({ onClose }) {
  const [form, setForm] = useState({
    vendor_name: "",
    description: "",
    oracle_department: "",
    oracle_department_name: "",
    purchase_order_number: "",
    status: "active",
  });
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const mutation = useCreateContract();

  function setField(k, v) { setForm((p) => ({ ...p, [k]: v })); }

  function setLineField(i, k, v) {
    setLines((prev) => prev.map((l, idx) => idx === i ? { ...l, [k]: v } : l));
  }

  function addLine() { setLines((prev) => [...prev, { ...EMPTY_LINE }]); }
  function removeLine(i) { setLines((prev) => prev.filter((_, idx) => idx !== i)); }

  function submit(e) {
    e.preventDefault();
    const parsedLines = lines
      .filter((l) => l.period_start && l.period_end && l.entered_amount && l.oracle_account_number)
      .map((l) => ({
        po_line_number: Number(l.po_line_number),
        oracle_account_number: l.oracle_account_number,
        oracle_account_sub_group: l.oracle_account_sub_group,
        activity_id: l.activity_id || null,
        period_start: l.period_start,
        period_end: l.period_end,
        billing_interval: l.billing_interval,
        entered_amount: parseFloat(l.entered_amount),
        notes: l.notes || null,
      }));
    mutation.mutate({ ...form, lines: parsedLines }, { onSuccess: onClose });
  }

  const { data: allAccounts = [] } = useAccounts();
  const { data: allActivities = [] } = useActivities(
    form.oracle_department ? { department_code: form.oracle_department } : undefined
  );

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 overflow-y-auto py-8" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl p-6 mx-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">New Contract</h2>
        <form onSubmit={submit} className="space-y-5 text-sm">

          {/* Contract header */}
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-0.5">Vendor Name *</label>
              <input required value={form.vendor_name} onChange={(e) => setField("vendor_name", e.target.value)} className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Department Code *</label>
              <input required value={form.oracle_department} onChange={(e) => setField("oracle_department", e.target.value)}
                placeholder="e.g. 1100" className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Department Name *</label>
              <input required value={form.oracle_department_name} onChange={(e) => setField("oracle_department_name", e.target.value)}
                placeholder="e.g. Engineering" className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">PO Number *</label>
              <input required value={form.purchase_order_number} onChange={(e) => setField("purchase_order_number", e.target.value)}
                placeholder="e.g. PO-83353" className={inputCls} />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Status</label>
              <select value={form.status} onChange={(e) => setField("status", e.target.value)} className={inputCls}>
                <option value="active">Active</option>
                <option value="pending">Pending</option>
                <option value="expired">Expired</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-0.5">Description</label>
              <textarea rows={2} value={form.description} onChange={(e) => setField("description", e.target.value)}
                className={`${inputCls} resize-none`} />
            </div>
          </div>

          {/* PO Lines */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">PO Lines</h3>
              <button type="button" onClick={addLine} className="text-xs text-blue-600 hover:text-blue-800 font-medium">
                + Add line
              </button>
            </div>
            <div className="space-y-4">
              {lines.map((line, i) => {
                const monthlyPreview = calcMonthlyPreview(line.entered_amount, line.billing_interval, line.period_start, line.period_end);
                const selectedAcct = allAccounts.find((a) => a.account_number === line.oracle_account_number);
                const matchingActivities = allActivities.filter(
                  (a) => !selectedAcct || a.account_id === selectedAcct.id
                );

                return (
                  <div key={i} className="bg-gray-50 rounded-lg p-3 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-medium text-gray-600">Line {i + 1}</span>
                      {lines.length > 1 && (
                        <button type="button" onClick={() => removeLine(i)} className="text-xs text-red-400 hover:text-red-600">Remove</button>
                      )}
                    </div>

                    {/* Account row */}
                    <div className="grid grid-cols-3 gap-2">
                      <div>
                        <label className="block text-xs text-gray-500 mb-0.5">PO Line # *</label>
                        <input required type="number" min="1" value={line.po_line_number}
                          onChange={(e) => setLineField(i, "po_line_number", e.target.value)}
                          className="w-full border rounded px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs text-gray-500 mb-0.5">Account Number *</label>
                        <select required value={line.oracle_account_number}
                          onChange={(e) => {
                            const acct = allAccounts.find((a) => a.account_number === e.target.value);
                            setLineField(i, "oracle_account_number", e.target.value);
                            setLineField(i, "oracle_account_sub_group", acct?.account_sub_group ?? "");
                            setLineField(i, "activity_id", null);
                          }}
                          className="w-full border rounded px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500">
                          <option value="">— Select account —</option>
                          {allAccounts.map((a) => (
                            <option key={a.account_number} value={a.account_number}>
                              {a.account_number}{a.account_desc ? ` — ${a.account_desc.slice(0, 40)}` : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs text-gray-500 mb-0.5">Activity ID</label>
                        <select value={line.activity_id ?? ""}
                          onChange={(e) => setLineField(i, "activity_id", e.target.value || null)}
                          disabled={!line.oracle_account_number}
                          className="w-full border rounded px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:opacity-40">
                          <option value="">— None —</option>
                          {matchingActivities.map((a) => (
                            <option key={a.activity_id} value={a.activity_id}>
                              {a.activity_id}{a.activity_id_desc ? ` — ${a.activity_id_desc}` : ""}
                            </option>
                          ))}
                        </select>
                      </div>
                      <div />
                    </div>

                    {/* Period / amount row */}
                    <div className="grid grid-cols-5 gap-2">
                      <div className="col-span-2">
                        <label className="block text-xs text-gray-500 mb-0.5">Service Start *</label>
                        <input required type="date" value={line.period_start}
                          onChange={(e) => setLineField(i, "period_start", e.target.value)}
                          className="w-full border rounded px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs text-gray-500 mb-0.5">Service End *</label>
                        <input required type="date" value={line.period_end}
                          onChange={(e) => setLineField(i, "period_end", e.target.value)}
                          className="w-full border rounded px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-500 mb-0.5">Interval</label>
                        <select value={line.billing_interval}
                          onChange={(e) => setLineField(i, "billing_interval", e.target.value)}
                          className="w-full border rounded px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500">
                          {INTERVAL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                        </select>
                      </div>
                      <div className="col-span-2">
                        <label className="block text-xs text-gray-500 mb-0.5">{INTERVAL_AMOUNT_LABEL[line.billing_interval]} *</label>
                        <input required type="number" min="0" step="0.01" value={line.entered_amount}
                          onChange={(e) => setLineField(i, "entered_amount", e.target.value)}
                          className="w-full border rounded px-1.5 py-1 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
                        {line.billing_interval !== "monthly" && monthlyPreview != null && (
                          <div className="text-xs text-gray-400 mt-0.5">{fmtUSD(monthlyPreview)}/mo</div>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {mutation.isError && <p className="text-xs text-red-600">Failed to create contract. Please try again.</p>}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-1.5 border rounded text-sm text-gray-600 hover:bg-gray-50">Cancel</button>
            <button type="submit" disabled={mutation.isPending}
              className="px-4 py-1.5 bg-blue-600 text-white rounded text-sm font-medium hover:bg-blue-700 disabled:opacity-50">
              {mutation.isPending ? "Creating…" : "Create Contract"}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ── ContractsPage ─────────────────────────────────────────────────────────────

export default function ContractsPage() {
  const { data: contracts = [], isLoading } = useContracts();
  const deleteContract = useDeleteContract();
  const deleteLine     = useDeleteContractLine();

  const [collapsed, setCollapsed] = useState(new Set());
  const [addingContract, setAddingContract] = useState(false);
  const [editingContract, setEditingContract] = useState(null);   // group object
  const [lineModal, setLineModal] = useState(null);               // { mode, contractId, deptCode, line? }

  // Filters (multi-select arrays, matching DropdownSlicer pattern)
  const [selVendors,         setSelVendors]         = useState([]);
  const [selDepts,           setSelDepts]           = useState([]);
  const [selStatus,          setSelStatus]          = useState([]);
  const [selCostElements,    setSelCostElements]    = useState([]);
  const [selAccountGroups,   setSelAccountGroups]   = useState([]);
  const [selAccountSubGroups, setSelAccountSubGroups] = useState([]);
  const [selActivityIds,     setSelActivityIds]     = useState([]);

  const { data: allAccountsForFilter = [] } = useAccounts();

  const groups = useMemo(() => buildPoGroups(contracts), [contracts]);

  // Cascading account filter options (mirrors ContractReportPage pattern)
  const availableAccountGroups = useMemo(() => (
    [...new Set(
      allAccountsForFilter
        .filter((a) => !selCostElements.length || selCostElements.includes(a.cost_element))
        .map((a) => a.account_group).filter(Boolean)
    )].sort()
  ), [allAccountsForFilter, selCostElements]);

  const effectiveSelAccountGroups = useMemo(
    () => selAccountGroups.filter((g) => availableAccountGroups.includes(g)),
    [selAccountGroups, availableAccountGroups]
  );

  const availableAccountSubGroups = useMemo(() => (
    [...new Set(
      allAccountsForFilter
        .filter((a) =>
          (!selCostElements.length || selCostElements.includes(a.cost_element)) &&
          (!effectiveSelAccountGroups.length || effectiveSelAccountGroups.includes(a.account_group))
        )
        .map((a) => a.account_sub_group).filter(Boolean)
    )].sort()
  ), [allAccountsForFilter, selCostElements, effectiveSelAccountGroups]);

  const effectiveSelAccountSubGroups = useMemo(
    () => selAccountSubGroups.filter((s) => availableAccountSubGroups.includes(s)),
    [selAccountSubGroups, availableAccountSubGroups]
  );

  // Build matching account number set for account-level filters
  const matchingAccountNumbers = useMemo(() => {
    if (!selCostElements.length && !effectiveSelAccountGroups.length && !effectiveSelAccountSubGroups.length) return null;
    return new Set(
      allAccountsForFilter
        .filter((a) =>
          (!selCostElements.length           || selCostElements.includes(a.cost_element)) &&
          (!effectiveSelAccountGroups.length  || effectiveSelAccountGroups.includes(a.account_group)) &&
          (!effectiveSelAccountSubGroups.length || effectiveSelAccountSubGroups.includes(a.account_sub_group))
        )
        .map((a) => a.account_number)
    );
  }, [allAccountsForFilter, selCostElements, effectiveSelAccountGroups, effectiveSelAccountSubGroups]);

  const filteredGroups = useMemo(() => {
    return groups.filter((g) => {
      if (selVendors.length && !selVendors.includes(g.vendor_name))                return false;
      if (selDepts.length   && !selDepts.includes(g.oracle_department_name))        return false;
      if (selStatus.length  && !selStatus.includes(g.status))                       return false;
      if (matchingAccountNumbers && !g.lines.some((l) => matchingAccountNumbers.has(l.oracle_account_number))) return false;
      if (selActivityIds.length  && !g.lines.some((l) => selActivityIds.includes(l.activity_id ?? "(Unassigned)"))) return false;
      return true;
    });
  }, [groups, selVendors, selDepts, selStatus, matchingAccountNumbers, selActivityIds]);

  // Static and dynamic option lists
  const filterOptions = useMemo(() => {
    const vendors     = [...new Set(groups.map((g) => g.vendor_name))].sort();
    const departments = [...new Set(groups.map((g) => g.oracle_department_name))].sort();
    const costElements = [...new Set(allAccountsForFilter.map((a) => a.cost_element).filter(Boolean))].sort();
    const assignedIds  = [...new Set(groups.flatMap((g) => g.lines.map((l) => l.activity_id).filter(Boolean)))].sort();
    const hasUnassigned = groups.some((g) => g.lines.some((l) => !l.activity_id));
    const activityIds  = hasUnassigned ? ["(Unassigned)", ...assignedIds] : assignedIds;
    return { vendors, departments, costElements, activityIds };
  }, [groups, allAccountsForFilter]);

  function toggleGroup(id) {
    setCollapsed((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function expandAll()   { setCollapsed(new Set()); }
  function collapseAll() { setCollapsed(new Set(filteredGroups.map((g) => g.id))); }

  function handleDeleteContract(group) {
    if (!window.confirm(`Delete contract for ${group.vendor_name} (${group.purchase_order_number})?`)) return;
    deleteContract.mutate(group.id);
  }

  function handleDeleteLine(line) {
    if (!window.confirm(`Delete line ${line.po_line_number}?`)) return;
    deleteLine.mutate({ contractId: line.contract_id, lineId: line.id });
  }

  const totalValue = filteredGroups.reduce((s, g) => s + g.contract_total, 0);
  const totalLines = filteredGroups.reduce((s, g) => s + g.lines.length, 0);

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="max-w-screen-2xl mx-auto px-6 py-8">

        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">Contract Database</h1>
            <p className="text-sm text-gray-500 mt-0.5">
              {filteredGroups.length} contract{filteredGroups.length !== 1 ? "s" : ""} · {totalLines} line{totalLines !== 1 ? "s" : ""} · {fmtUSD(totalValue)} total
            </p>
          </div>
          <button onClick={() => setAddingContract(true)}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700 shadow-sm">
            + New Contract
          </button>
        </div>

        {/* Filters + toolbar */}
        <div className="bg-white border border-gray-100 rounded-xl px-4 py-3 mb-4">
          <div className="grid grid-cols-3 gap-3">
            <DropdownSlicer title="Vendor"           options={filterOptions.vendors}     selected={selVendors}               onToggle={setSelVendors}          searchable />
            <DropdownSlicer title="Department"       options={filterOptions.departments} selected={selDepts}                 onToggle={setSelDepts}            searchable />
            <DropdownSlicer title="Status"           options={["active","pending","expired","cancelled"]} selected={selStatus} onToggle={setSelStatus} />
            <DropdownSlicer title="Account Group"    options={availableAccountGroups}    selected={effectiveSelAccountGroups}    onToggle={setSelAccountGroups}    searchable />
            <DropdownSlicer title="Account Sub Group" options={availableAccountSubGroups} selected={effectiveSelAccountSubGroups} onToggle={setSelAccountSubGroups} searchable />
            <DropdownSlicer title="Cost Element"     options={filterOptions.costElements} selected={selCostElements}          onToggle={(v) => { setSelCostElements(v); setSelAccountGroups([]); setSelAccountSubGroups([]); }} searchable />
            <DropdownSlicer title="Activity ID"      options={filterOptions.activityIds} selected={selActivityIds}           onToggle={setSelActivityIds}      searchable />
            <div />
            <div className="flex justify-end items-end gap-1">
              <button onClick={expandAll}   className="px-2.5 py-1.5 text-xs border rounded hover:bg-gray-50 text-gray-600">Expand All</button>
              <button onClick={collapseAll} className="px-2.5 py-1.5 text-xs border rounded hover:bg-gray-50 text-gray-600">Collapse All</button>
            </div>
          </div>
        </div>

        {/* Flat table */}
        <div className="bg-white rounded-xl border border-gray-200 shadow-sm overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="bg-gray-50 border-b border-gray-200 text-left">
                <th className="w-6" />
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide min-w-[160px]">Vendor</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide min-w-[140px]">Department</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide min-w-[130px]">PO Number</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Line #</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Account</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Activity ID</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Period</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide text-center">Mo</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Interval</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide text-right">Monthly</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide text-right">Total</th>
                <th className="px-3 py-3 text-xs font-semibold text-gray-600 uppercase tracking-wide">Actions</th>
              </tr>
            </thead>
            <tbody>
              {isLoading && (
                <tr><td colSpan={13} className="px-6 py-12 text-center text-gray-400">Loading…</td></tr>
              )}
              {!isLoading && filteredGroups.length === 0 && (
                <tr><td colSpan={13} className="px-6 py-12 text-center text-gray-400">No contracts found.</td></tr>
              )}
              {filteredGroups.map((group) => (
                <PoGroupRow
                  key={group.id}
                  group={group}
                  collapsed={collapsed.has(group.id)}
                  onToggle={() => toggleGroup(group.id)}
                  onEditContract={() => setEditingContract(group)}
                  onDeleteContract={() => handleDeleteContract(group)}
                  onAddLine={() => setLineModal({ mode: "add", contractId: group.id, deptCode: group.oracle_department })}
                  onEditLine={(line) => setLineModal({ mode: "edit", contractId: group.id, deptCode: group.oracle_department, line })}
                  onDeleteLine={handleDeleteLine}
                />
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Modals */}
      {addingContract && <AddContractModal onClose={() => setAddingContract(false)} />}
      {editingContract && (
        <EditContractModal group={editingContract} onClose={() => setEditingContract(null)} />
      )}
      {lineModal && (
        <LineModal
          mode={lineModal.mode}
          contractId={lineModal.contractId}
          deptCode={lineModal.deptCode}
          line={lineModal.line}
          onClose={() => setLineModal(null)}
        />
      )}
    </div>
  );
}
