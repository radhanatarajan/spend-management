import { useState } from "react";
import {
  useContracts,
  useCreateContract,
  useUpdateContract,
  useDeleteContract,
  useAddContractLine,
  useUpdateContractLine,
  useDeleteContractLine,
} from "../../data/contracts";

// ── Formatting helpers ────────────────────────────────────────────────────────

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

// ── Billing interval helpers ──────────────────────────────────────────────────

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

// ── Grouping helpers ──────────────────────────────────────────────────────────

function groupContracts(contracts) {
  const map = new Map();
  for (const c of contracts) {
    const key = `${c.vendor_name}|${c.oracle_department}|${c.oracle_account_number}|${c.purchase_order_number}`;
    if (!map.has(key)) {
      map.set(key, {
        key,
        vendor_name: c.vendor_name,
        oracle_department: c.oracle_department,
        oracle_department_name: c.oracle_department_name,
        oracle_account_number: c.oracle_account_number,
        oracle_account_sub_group: c.oracle_account_sub_group,
        purchase_order_number: c.purchase_order_number,
        description: c.description,
        status: c.status,
        contract_ids: [],
        lines: [],
      });
    }
    const g = map.get(key);
    g.contract_ids.push(c.id);
    for (const line of c.lines) g.lines.push({ ...line, contract_id: c.id });
  }
  for (const g of map.values()) {
    g.lines.sort((a, b) => a.period_start.localeCompare(b.period_start));
    g.contract_total = g.lines.reduce((s, l) => s + Number(l.total_amount), 0);
    // status from the contract that owns the last line
    const lastContractId = g.lines.at(-1)?.contract_id ?? g.contract_ids[0];
    const lastContract = contracts.find((c) => c.id === lastContractId);
    if (lastContract) g.status = lastContract.status;
  }
  return Array.from(map.values());
}

function isMultiYearGroup(lines) {
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

// ── Sub-components ────────────────────────────────────────────────────────────

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


function AddLineForm({ contractId, onDone }) {
  const [form, setForm] = useState({ po_line_number: "", period_start: "", period_end: "", billing_interval: "monthly", entered_amount: "" });
  const mutation = useAddContractLine();

  function set(k, v) { setForm((p) => ({ ...p, [k]: v })); }

  const monthlyPreview = calcMonthlyPreview(form.entered_amount, form.billing_interval, form.period_start, form.period_end);

  function submit(e) {
    e.preventDefault();
    mutation.mutate(
      { contractId, ...form, po_line_number: Number(form.po_line_number), entered_amount: parseFloat(form.entered_amount) },
      { onSuccess: onDone }
    );
  }

  return (
    <form onSubmit={submit} className="grid grid-cols-6 gap-2 items-end mt-2 text-xs">
      <div>
        <label className="block text-gray-500 mb-0.5">PO Line #</label>
        <input required type="number" min="1" value={form.po_line_number} onChange={(e) => set("po_line_number", e.target.value)}
          className="w-full border rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500" />
      </div>
      <div>
        <label className="block text-gray-500 mb-0.5">Service Start</label>
        <input required type="date" value={form.period_start} onChange={(e) => set("period_start", e.target.value)}
          className="w-full border rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500" />
      </div>
      <div>
        <label className="block text-gray-500 mb-0.5">Service End</label>
        <input required type="date" value={form.period_end} onChange={(e) => set("period_end", e.target.value)}
          className="w-full border rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500" />
      </div>
      <div>
        <label className="block text-gray-500 mb-0.5">Interval</label>
        <select value={form.billing_interval} onChange={(e) => set("billing_interval", e.target.value)}
          className="w-full border rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500">
          {INTERVAL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
        </select>
      </div>
      <div>
        <label className="block text-gray-500 mb-0.5">{INTERVAL_AMOUNT_LABEL[form.billing_interval]}</label>
        <input required type="number" min="0" step="0.01" value={form.entered_amount} onChange={(e) => set("entered_amount", e.target.value)}
          className="w-full border rounded px-1.5 py-1 focus:outline-none focus:ring-1 focus:ring-blue-500" />
        {form.billing_interval !== "monthly" && monthlyPreview != null && (
          <div className="text-gray-400 mt-0.5">{fmtUSD(monthlyPreview)}/mo</div>
        )}
      </div>
      <div className="flex gap-1">
        <button type="submit" disabled={mutation.isPending}
          className="px-3 py-1 bg-blue-600 text-white rounded text-xs font-medium hover:bg-blue-700 disabled:opacity-50">
          {mutation.isPending ? "Adding…" : "Add"}
        </button>
        <button type="button" onClick={onDone} className="px-3 py-1 border rounded text-xs text-gray-600 hover:bg-gray-50">
          Cancel
        </button>
      </div>
    </form>
  );
}

function ContractLineRow({ line, onDelete }) {
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState({
    po_line_number: String(line.po_line_number),
    period_start: line.period_start,
    period_end: line.period_end,
    billing_interval: line.billing_interval,
    entered_amount: String(line.entered_amount),
    notes: line.notes ?? "",
  });
  const mutation = useUpdateContractLine();

  function set(k, v) { setForm((p) => ({ ...p, [k]: v })); }

  function save() {
    const parsed = parseFloat(form.entered_amount.replace(/,/g, ""));
    if (isNaN(parsed) || parsed <= 0) return;
    mutation.mutate(
      {
        contractId: line.contract_id,
        lineId: line.id,
        po_line_number: Number(form.po_line_number),
        period_start: form.period_start,
        period_end: form.period_end,
        billing_interval: form.billing_interval,
        entered_amount: parsed.toFixed(2),
        notes: form.notes || null,
      },
      { onSuccess: () => setEditing(false) }
    );
  }

  const monthlyPreview = calcMonthlyPreview(form.entered_amount, form.billing_interval, form.period_start, form.period_end);

  if (editing) {
    return (
      <tr className="bg-blue-50">
        <td className="py-1.5 pr-2">
          <input type="number" min="1" value={form.po_line_number} onChange={(e) => set("po_line_number", e.target.value)}
            className="w-14 border border-blue-300 rounded px-1.5 py-0.5 text-xs font-mono focus:outline-none focus:ring-1 focus:ring-blue-500" />
        </td>
        <td className="py-1.5 pr-2">
          <div className="flex items-center gap-1">
            <input type="date" value={form.period_start} onChange={(e) => set("period_start", e.target.value)}
              className="border border-blue-300 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
            <span className="text-gray-400">–</span>
            <input type="date" value={form.period_end} onChange={(e) => set("period_end", e.target.value)}
              className="border border-blue-300 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500" />
          </div>
        </td>
        <td className="py-1.5 text-gray-400 text-xs">
          {form.period_start && form.period_end ? (() => {
            const [sy, sm] = form.period_start.split("-").map(Number);
            const [ey, em] = form.period_end.split("-").map(Number);
            return (ey - sy) * 12 + (em - sm) + 1;
          })() : "—"}
        </td>
        <td className="py-1.5 pr-2">
          <select value={form.billing_interval} onChange={(e) => set("billing_interval", e.target.value)}
            className="border border-blue-300 rounded px-1.5 py-0.5 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500">
            {INTERVAL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </select>
        </td>
        <td className="py-1.5 pr-2 text-right">
          <input type="text" value={form.entered_amount} onChange={(e) => set("entered_amount", e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }}
            className="w-28 border border-blue-400 rounded px-1.5 py-0.5 text-xs font-mono text-right focus:outline-none focus:ring-1 focus:ring-blue-500" />
        </td>
        <td className="py-1.5 text-right font-mono text-gray-500 text-xs">
          {monthlyPreview != null ? fmtUSD(monthlyPreview) : "—"}
        </td>
        <td className="py-1.5 text-right font-mono text-gray-500 text-xs">—</td>
        <td className="py-1.5 pl-4">
          <div className="flex items-center gap-2">
            <button onClick={save} disabled={mutation.isPending}
              className="text-xs text-blue-600 hover:text-blue-800 font-medium disabled:opacity-50">
              {mutation.isPending ? "…" : "Save"}
            </button>
            <button onClick={() => setEditing(false)} className="text-xs text-gray-400 hover:text-gray-600">
              Cancel
            </button>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className="hover:bg-white group">
      <td className="py-1.5 font-mono text-gray-700">Line {line.po_line_number}</td>
      <td className="py-1.5 text-gray-600">{fmtPeriod(line.period_start, line.period_end)}</td>
      <td className="py-1.5 text-gray-500">{line.months_in_period}</td>
      <td className="py-1.5"><IntervalBadge interval={line.billing_interval} /></td>
      <td className="py-1.5 text-right">
        <div className="text-right font-mono">{fmtUSD(line.entered_amount)}</div>
        {line.billing_interval !== "monthly" && (
          <div className="text-xs text-gray-400 font-mono">{fmtUSD(line.monthly_amount)}/mo</div>
        )}
      </td>
      <td className="py-1.5 text-right font-mono text-gray-600">{fmtUSD(line.monthly_amount)}</td>
      <td className="py-1.5 text-right font-mono font-medium text-gray-800">{fmtUSD(line.total_amount)}</td>
      <td className="py-1.5 pl-4">
        <div className="flex items-center gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
          <button onClick={() => setEditing(true)} className="text-xs text-blue-400 hover:text-blue-600">
            Edit
          </button>
          <button onClick={onDelete} className="text-xs text-red-300 hover:text-red-500">
            ✕
          </button>
        </div>
      </td>
    </tr>
  );
}

function ContractGroupRow({ group, onDeleteContracts }) {
  const [expanded, setExpanded] = useState(false);
  const [addingLine, setAddingLine] = useState(false);
  const [editing, setEditing] = useState(false);
  const deleteLine = useDeleteContractLine();
  const multiYear = isMultiYearGroup(group.lines);

  // Add new lines to the contract that owns the last existing line
  const addToContractId = group.lines.at(-1)?.contract_id ?? group.contract_ids[0];

  return (
    <>
      <tr className="hover:bg-gray-50 cursor-pointer" onClick={() => setExpanded((p) => !p)}>
        <td className="px-4 py-3 w-6">
          <svg className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? "rotate-90" : ""}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </td>
        <td className="px-4 py-3 text-sm">
          <span className="font-medium text-gray-900">{group.vendor_name}</span>
          {multiYear && (
            <span className="ml-2 text-[10px] font-semibold uppercase tracking-wide px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-600">
              Multi-year
            </span>
          )}
        </td>
        <td className="px-4 py-3 text-sm text-gray-600">{group.oracle_department_name}</td>
        <td className="px-4 py-3 text-sm text-gray-500 font-mono">{group.oracle_account_number}</td>
        <td className="px-4 py-3 text-sm text-gray-500 font-mono">{group.purchase_order_number}</td>
        <td className="px-4 py-3 text-sm text-gray-600">{group.lines.length} year{group.lines.length !== 1 ? "s" : ""}</td>
        <td className="px-4 py-3 text-sm font-medium text-gray-900 text-right font-mono">{fmtUSD(group.contract_total)}</td>
        <td className="px-4 py-3"><StatusBadge status={group.status} /></td>
        <td className="px-4 py-3 text-right" onClick={(e) => e.stopPropagation()}>
          <div className="flex items-center justify-end gap-3">
            <button onClick={() => setEditing(true)} className="text-blue-400 hover:text-blue-600 text-xs">
              Edit
            </button>
            <button
              onClick={() => {
                if (confirm(`Delete all contracts for ${group.vendor_name} / ${group.purchase_order_number}?`)) {
                  onDeleteContracts(group.contract_ids);
                }
              }}
              className="text-red-400 hover:text-red-600 text-xs"
            >
              Delete
            </button>
          </div>
        </td>
      </tr>

      {editing && <EditContractModal group={group} onClose={() => setEditing(false)} />}

      {expanded && (
        <tr>
          <td colSpan={9} className="px-0 py-0 bg-slate-50 border-b border-gray-100">
            <div className="px-10 py-3">
              {group.description && (
                <p className="text-xs text-gray-500 mb-3">{group.description}</p>
              )}

              <table className="w-full text-xs">
                <thead>
                  <tr className="text-gray-400 uppercase tracking-wide">
                    <th className="text-left pb-1 font-medium">PO Line</th>
                    <th className="text-left pb-1 font-medium">Service Period</th>
                    <th className="text-left pb-1 font-medium">Months</th>
                    <th className="text-left pb-1 font-medium">Interval</th>
                    <th className="text-right pb-1 font-medium">Entered Amount</th>
                    <th className="text-right pb-1 font-medium">Monthly</th>
                    <th className="text-right pb-1 font-medium">Period Total</th>
                    <th className="pb-1"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {group.lines.map((line) => (
                    <ContractLineRow
                      key={line.id}
                      line={line}
                      onDelete={() => { if (confirm("Remove this line?")) deleteLine.mutate({ contractId: line.contract_id, lineId: line.id }); }}
                    />
                  ))}
                </tbody>
                {group.lines.length > 1 && (
                  <tfoot>
                    <tr className="border-t border-gray-200">
                      <td colSpan={6} className="pt-1.5 text-gray-400 font-medium">Contract Total</td>
                      <td className="pt-1.5 text-right font-mono font-semibold text-gray-900">
                        {fmtUSD(group.contract_total)}
                      </td>
                      <td />
                    </tr>
                  </tfoot>
                )}
              </table>

              {addingLine ? (
                <AddLineForm contractId={addToContractId} onDone={() => setAddingLine(false)} />
              ) : (
                <button
                  onClick={() => setAddingLine(true)}
                  className="mt-2 text-xs text-blue-600 hover:text-blue-800 font-medium"
                >
                  + Add line
                </button>
              )}
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function EditContractModal({ group, onClose }) {
  const [form, setForm] = useState({
    vendor_name: group.vendor_name,
    description: group.description ?? "",
    oracle_department: group.oracle_department,
    oracle_department_name: group.oracle_department_name,
    oracle_account_number: group.oracle_account_number,
    oracle_account_sub_group: group.oracle_account_sub_group,
    purchase_order_number: group.purchase_order_number,
    status: group.status,
  });
  const mutation = useUpdateContract();

  function setField(k, v) { setForm((p) => ({ ...p, [k]: v })); }

  function submit(e) {
    e.preventDefault();
    let remaining = group.contract_ids.length;
    group.contract_ids.forEach((id) => {
      mutation.mutate(
        { id, ...form },
        { onSuccess: () => { remaining -= 1; if (remaining === 0) onClose(); } }
      );
    });
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 py-8" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 mx-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Edit Contract</h2>
        <form onSubmit={submit} className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-0.5">Vendor Name *</label>
              <input required value={form.vendor_name} onChange={(e) => setField("vendor_name", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Department Code *</label>
              <input required value={form.oracle_department} onChange={(e) => setField("oracle_department", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Department Name *</label>
              <input required value={form.oracle_department_name} onChange={(e) => setField("oracle_department_name", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Account Number *</label>
              <input required value={form.oracle_account_number} onChange={(e) => setField("oracle_account_number", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Account Sub-Group *</label>
              <input required value={form.oracle_account_sub_group} onChange={(e) => setField("oracle_account_sub_group", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">PO Number *</label>
              <input required value={form.purchase_order_number} onChange={(e) => setField("purchase_order_number", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Status</label>
              <select value={form.status} onChange={(e) => setField("status", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500">
                <option value="active">Active</option>
                <option value="pending">Pending</option>
                <option value="expired">Expired</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-0.5">Description</label>
              <textarea rows={2} value={form.description} onChange={(e) => setField("description", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none" />
            </div>
          </div>

          {mutation.isError && (
            <p className="text-xs text-red-600">Failed to save changes. Please try again.</p>
          )}
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={onClose} className="px-4 py-1.5 border rounded text-sm text-gray-600 hover:bg-gray-50">
              Cancel
            </button>
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

const EMPTY_LINE = { po_line_number: "", period_start: "", period_end: "", billing_interval: "monthly", entered_amount: "", notes: "" };

function AddContractModal({ onClose }) {
  const [form, setForm] = useState({
    vendor_name: "", description: "", oracle_department: "", oracle_department_name: "",
    oracle_account_number: "", oracle_account_sub_group: "Software Licenses",
    purchase_order_number: "", status: "active",
  });
  const [lines, setLines] = useState([{ ...EMPTY_LINE }]);
  const mutation = useCreateContract();

  function setField(k, v) { setForm((p) => ({ ...p, [k]: v })); }
  function setLine(i, k, v) { setLines((prev) => prev.map((l, idx) => idx === i ? { ...l, [k]: v } : l)); }
  function addLine() { setLines((prev) => [...prev, { ...EMPTY_LINE }]); }
  function removeLine(i) { setLines((prev) => prev.filter((_, idx) => idx !== i)); }

  function submit(e) {
    e.preventDefault();
    const parsedLines = lines
      .filter((l) => l.period_start && l.period_end && l.entered_amount)
      .map((l) => ({
        po_line_number: Number(l.po_line_number),
        period_start: l.period_start,
        period_end: l.period_end,
        billing_interval: l.billing_interval,
        entered_amount: parseFloat(l.entered_amount),
        notes: l.notes || null,
      }));
    mutation.mutate({ ...form, lines: parsedLines }, { onSuccess: onClose });
  }

  return (
    <div className="fixed inset-0 bg-black/30 flex items-center justify-center z-50 overflow-y-auto py-8" onClick={onClose}>
      <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl p-6 mx-4" onClick={(e) => e.stopPropagation()}>
        <h2 className="text-lg font-semibold text-gray-900 mb-4">New Contract</h2>
        <form onSubmit={submit} className="space-y-5 text-sm">

          {/* Contract header */}
          <div className="grid grid-cols-2 gap-3">
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-0.5">Vendor Name *</label>
              <input required value={form.vendor_name} onChange={(e) => setField("vendor_name", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Department Code *</label>
              <input required value={form.oracle_department} onChange={(e) => setField("oracle_department", e.target.value)}
                placeholder="e.g. 1100"
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Department Name *</label>
              <input required value={form.oracle_department_name} onChange={(e) => setField("oracle_department_name", e.target.value)}
                placeholder="e.g. Engineering"
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Account Number *</label>
              <input required value={form.oracle_account_number} onChange={(e) => setField("oracle_account_number", e.target.value)}
                placeholder="e.g. ACC-6385"
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Account Sub-Group *</label>
              <input required value={form.oracle_account_sub_group} onChange={(e) => setField("oracle_account_sub_group", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">PO Number *</label>
              <input required value={form.purchase_order_number} onChange={(e) => setField("purchase_order_number", e.target.value)}
                placeholder="e.g. PO-83353"
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500" />
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-0.5">Status</label>
              <select value={form.status} onChange={(e) => setField("status", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500">
                <option value="active">Active</option>
                <option value="pending">Pending</option>
                <option value="expired">Expired</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
            <div className="col-span-2">
              <label className="block text-xs text-gray-500 mb-0.5">Description</label>
              <textarea rows={2} value={form.description} onChange={(e) => setField("description", e.target.value)}
                className="w-full border rounded px-2 py-1.5 focus:outline-none focus:ring-1 focus:ring-blue-500 resize-none" />
            </div>
          </div>

          {/* PO Lines */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-xs font-semibold text-gray-700 uppercase tracking-wide">PO Lines</h3>
              <button type="button" onClick={addLine}
                className="text-xs text-blue-600 hover:text-blue-800 font-medium">
                + Add line
              </button>
            </div>
            <div className="space-y-2">
              {lines.map((line, i) => {
                const monthlyPreview = calcMonthlyPreview(line.entered_amount, line.billing_interval, line.period_start, line.period_end);
                return (
                  <div key={i} className="grid grid-cols-10 gap-2 items-end bg-gray-50 rounded-lg p-2">
                    <div className="col-span-1">
                      <label className="block text-xs text-gray-500 mb-0.5">PO Line #</label>
                      <input required type="number" min="1" value={line.po_line_number}
                        onChange={(e) => setLine(i, "po_line_number", e.target.value)}
                        className="w-full border rounded px-1.5 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-xs text-gray-500 mb-0.5">Service Start *</label>
                      <input required type="date" value={line.period_start}
                        onChange={(e) => setLine(i, "period_start", e.target.value)}
                        className="w-full border rounded px-1.5 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-xs text-gray-500 mb-0.5">Service End *</label>
                      <input required type="date" value={line.period_end}
                        onChange={(e) => setLine(i, "period_end", e.target.value)}
                        className="w-full border rounded px-1.5 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-xs text-gray-500 mb-0.5">Interval *</label>
                      <select value={line.billing_interval}
                        onChange={(e) => setLine(i, "billing_interval", e.target.value)}
                        className="w-full border rounded px-1.5 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500">
                        {INTERVAL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                      </select>
                    </div>
                    <div className="col-span-2">
                      <label className="block text-xs text-gray-500 mb-0.5">{INTERVAL_AMOUNT_LABEL[line.billing_interval]} *</label>
                      <input required type="number" min="0" step="0.01" value={line.entered_amount}
                        onChange={(e) => setLine(i, "entered_amount", e.target.value)}
                        placeholder="0.00"
                        className="w-full border rounded px-1.5 py-1 text-sm focus:outline-none focus:ring-1 focus:ring-blue-500" />
                      {line.billing_interval !== "monthly" && monthlyPreview != null && (
                        <div className="text-xs text-gray-400 mt-0.5">{fmtUSD(monthlyPreview)}/mo</div>
                      )}
                    </div>
                    <div className="col-span-1 flex items-end justify-center pb-0.5">
                      {lines.length > 1 && (
                        <button type="button" onClick={() => removeLine(i)}
                          className="text-red-300 hover:text-red-500 text-sm leading-none">
                          ✕
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </div>

          {mutation.isError && (
            <p className="text-xs text-red-600">Failed to create contract. Please try again.</p>
          )}
          <div className="flex justify-end gap-2 pt-2">
            <button type="button" onClick={onClose} className="px-4 py-1.5 border rounded text-sm text-gray-600 hover:bg-gray-50">
              Cancel
            </button>
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

// ── Page ─────────────────────────────────────────────────────────────────────

export default function ContractsPage() {
  const { data: contracts, isLoading, isError } = useContracts();
  const deleteContract = useDeleteContract();
  const [showAdd, setShowAdd] = useState(false);
  const [statusFilter, setStatusFilter] = useState("all");

  const allGroups = groupContracts(contracts ?? []);
  const visibleGroups = allGroups.filter(
    (g) => statusFilter === "all" || g.status === statusFilter
  );

  const grandTotal = visibleGroups.reduce((sum, g) => sum + g.contract_total, 0);

  function handleDeleteContracts(ids) {
    ids.forEach((id) => deleteContract.mutate(id));
  }

  return (
    <div className="p-6">
      <div className="max-w-screen-2xl mx-auto">
        {/* Header */}
        <div className="flex items-start justify-between mb-6">
          <div>
            <h1 className="text-2xl font-semibold text-gray-900">Contract Database</h1>
            <p className="text-sm text-gray-500 mt-0.5">Software license agreements — monthly breakout for planning</p>
          </div>
          <button
            onClick={() => setShowAdd(true)}
            className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-lg hover:bg-blue-700"
          >
            + New Contract
          </button>
        </div>

        {/* Filters + summary strip */}
        <div className="flex items-center gap-4 mb-4">
          <div className="flex items-center gap-1.5 text-sm">
            {["all", "active", "pending", "expired", "cancelled"].map((s) => (
              <button
                key={s}
                onClick={() => setStatusFilter(s)}
                className={`px-3 py-1 rounded-full text-xs font-medium capitalize border transition-colors ${
                  statusFilter === s
                    ? "bg-blue-600 text-white border-blue-600"
                    : "border-gray-200 text-gray-600 hover:border-gray-300"
                }`}
              >
                {s}
              </button>
            ))}
          </div>
          <span className="ml-auto text-sm text-gray-500">
            {visibleGroups.length} PO{visibleGroups.length !== 1 ? "s" : ""} &nbsp;·&nbsp;
            <span className="font-medium text-gray-800">{fmtUSD(grandTotal)}</span> total value
          </span>
        </div>

        {/* Table */}
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
          {isLoading ? (
            <div className="p-8 text-center text-sm text-gray-400">Loading contracts…</div>
          ) : isError ? (
            <div className="p-8 text-center text-sm text-red-500">Failed to load contracts.</div>
          ) : visibleGroups.length === 0 ? (
            <div className="p-8 text-center text-sm text-gray-400">No contracts found. Click "New Contract" to add one.</div>
          ) : (
            <table className="w-full">
              <thead className="bg-gray-50 border-b border-gray-200">
                <tr className="text-xs font-medium text-gray-500 uppercase tracking-wide">
                  <th className="px-4 py-3 w-6" />
                  <th className="px-4 py-3 text-left">Vendor</th>
                  <th className="px-4 py-3 text-left">Department</th>
                  <th className="px-4 py-3 text-left">Account</th>
                  <th className="px-4 py-3 text-left">PO Number</th>
                  <th className="px-4 py-3 text-left">Terms</th>
                  <th className="px-4 py-3 text-right">Contract Value</th>
                  <th className="px-4 py-3 text-left">Status</th>
                  <th className="px-4 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {visibleGroups.map((group) => (
                  <ContractGroupRow key={group.key} group={group} onDeleteContracts={handleDeleteContracts} />
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {showAdd && <AddContractModal onClose={() => setShowAdd(false)} />}
    </div>
  );
}
