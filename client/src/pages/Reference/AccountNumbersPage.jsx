import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import DropdownSlicer from "../../components/DropdownSlicer";
import {
  useAccounts, useCreateAccount, useDeleteAccount, useUpdateAccount,
} from "../../data/reference";

const EMPTY_FORM = { account_desc: "", account_group: "", account_sub_group: "", cost_element: "" };

function matchesText(acct, q) {
  if (!q) return true;
  const t = q.toLowerCase();
  return (
    acct.account_number.toLowerCase().includes(t) ||
    (acct.account_desc ?? "").toLowerCase().includes(t) ||
    acct.account_group.toLowerCase().includes(t) ||
    (acct.account_sub_group ?? "").toLowerCase().includes(t) ||
    acct.cost_element.toLowerCase().includes(t)
  );
}

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-md mx-4 p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function AccountForm({ initial = EMPTY_FORM, isEdit, accountNumber, editingId, onSubmit, onClose, isPending, allAccounts = [] }) {
  const [form, setForm] = useState(initial);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const isDuplicate = form.account_group.trim() !== "" && form.cost_element.trim() !== "" &&
    allAccounts.some(a =>
      a.id !== editingId &&
      a.account_group === form.account_group.trim() &&
      (a.account_sub_group ?? "") === (form.account_sub_group ?? "").trim() &&
      a.cost_element === form.cost_element.trim()
    );

  const inp = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500";

  return (
    <form onSubmit={e => { e.preventDefault(); if (!isDuplicate) onSubmit(form); }}>
      <div className="space-y-3">
        {isEdit && accountNumber && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Account Number</label>
            <div className="px-3 py-2 text-sm font-mono text-gray-600 bg-gray-50 border border-gray-200 rounded-lg">{accountNumber}</div>
          </div>
        )}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
          <input
            className={inp}
            value={form.account_desc ?? ""}
            onChange={e => set("account_desc", e.target.value || null)}
            placeholder="e.g. DC Office Rent — Facilities"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Account Group</label>
          <input
            required
            className={inp}
            value={form.account_group}
            onChange={e => set("account_group", e.target.value)}
            placeholder="e.g. R&D"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Account Sub-Group</label>
          <input
            className={inp}
            value={form.account_sub_group ?? ""}
            onChange={e => set("account_sub_group", e.target.value || null)}
            placeholder="Optional"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Cost Element</label>
          <input
            required
            className={inp}
            value={form.cost_element}
            onChange={e => set("cost_element", e.target.value)}
            placeholder="e.g. Licenses"
          />
        </div>
        {isDuplicate && (
          <p className="text-xs text-red-600">An account with this Group / Sub-Group / Cost Element combination already exists.</p>
        )}
      </div>
      <div className="flex justify-end gap-2 mt-5">
        <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Cancel</button>
        <button
          type="submit"
          disabled={isPending || isDuplicate}
          className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
        >
          {isPending ? "Saving…" : isEdit ? "Save Changes" : "Create"}
        </button>
      </div>
    </form>
  );
}

export default function AccountNumbersPage() {
  const { user } = useAuth();
  const canWrite = user?.role !== "READ_ONLY";

  const [selectedGroups, setSelectedGroups] = useState([]);
  const [selectedSubGroups, setSelectedSubGroups] = useState([]);
  const [selectedCostElements, setSelectedCostElements] = useState([]);
  const [filterText, setFilterText] = useState("");

  const { data: allAccounts = [], isLoading, error } = useAccounts();

  // Each slicer's options narrow based on the OTHER two active selections (faceted)
  const groupOptions = [...new Set(
    allAccounts
      .filter(a => selectedSubGroups.length === 0 || selectedSubGroups.includes(a.account_sub_group))
      .filter(a => selectedCostElements.length === 0 || selectedCostElements.includes(a.cost_element))
      .map(a => a.account_group)
  )].sort();

  const subGroupOptions = [...new Set(
    allAccounts
      .filter(a => selectedGroups.length === 0 || selectedGroups.includes(a.account_group))
      .filter(a => selectedCostElements.length === 0 || selectedCostElements.includes(a.cost_element))
      .map(a => a.account_sub_group).filter(Boolean)
  )].sort();

  const costElementOptions = [...new Set(
    allAccounts
      .filter(a => selectedGroups.length === 0 || selectedGroups.includes(a.account_group))
      .filter(a => selectedSubGroups.length === 0 || selectedSubGroups.includes(a.account_sub_group))
      .map(a => a.cost_element)
  )].sort();

  const displayAccounts = allAccounts.filter(a => {
    if (selectedGroups.length > 0 && !selectedGroups.includes(a.account_group)) return false;
    if (selectedSubGroups.length > 0 && !selectedSubGroups.includes(a.account_sub_group)) return false;
    if (selectedCostElements.length > 0 && !selectedCostElements.includes(a.cost_element)) return false;
    return matchesText(a, filterText.trim());
  });

  const hasFilters = selectedGroups.length > 0 || selectedSubGroups.length > 0 || selectedCostElements.length > 0 || !!filterText;

  const create = useCreateAccount();
  const update = useUpdateAccount();
  const del = useDeleteAccount();

  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delConfirm, setDelConfirm] = useState(null);
  const [apiError, setApiError] = useState(null);

  function clearFilters() {
    setSelectedGroups([]);
    setSelectedSubGroups([]);
    setSelectedCostElements([]);
    setFilterText("");
  }

  function handleCreate(form) {
    setApiError(null);
    create.mutate(form, {
      onSuccess: () => setShowAdd(false),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to create account"),
    });
  }

  function handleUpdate(form) {
    setApiError(null);
    update.mutate({
      id: editing.id,
      account_desc: form.account_desc,
      account_group: form.account_group,
      account_sub_group: form.account_sub_group,
      cost_element: form.cost_element,
    }, {
      onSuccess: () => setEditing(null),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to update account"),
    });
  }

  function handleDelete(id) {
    setApiError(null);
    del.mutate(id, {
      onSuccess: () => setDelConfirm(null),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to delete account"),
    });
  }

  return (
    <div className="p-6 max-w-screen-lg mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Account Numbers</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage account number master data</p>
        </div>
        {canWrite && (
          <button
            onClick={() => { setApiError(null); setShowAdd(true); }}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700"
          >
            <span className="text-lg leading-none">+</span> Add Account
          </button>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <input
          type="text"
          className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 bg-white min-w-[200px]"
          placeholder="Search accounts…"
          value={filterText}
          onChange={e => setFilterText(e.target.value)}
        />
        <DropdownSlicer
          title="Acct. Group"
          options={groupOptions}
          selected={selectedGroups}
          onToggle={setSelectedGroups}
          searchable
        />
        <DropdownSlicer
          title="Sub-Group"
          options={subGroupOptions}
          selected={selectedSubGroups}
          onToggle={setSelectedSubGroups}
          searchable
        />
        <DropdownSlicer
          title="Cost Element"
          options={costElementOptions}
          selected={selectedCostElements}
          onToggle={setSelectedCostElements}
          searchable
        />
        {hasFilters && (
          <button onClick={clearFilters} className="text-xs text-gray-500 hover:text-gray-800 px-2">Clear all</button>
        )}
      </div>

      {apiError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">{apiError}</div>
      )}

      {isLoading && <div className="text-sm text-gray-500">Loading…</div>}
      {error && <div className="text-sm text-red-600">Failed to load accounts.</div>}

      {!isLoading && !error && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide w-40">Account #</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Description</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Group</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Sub-Group</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Cost Element</th>
                {canWrite && <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {displayAccounts.length === 0 && (
                <tr><td colSpan={6} className="px-4 py-8 text-center text-gray-400 text-sm">No accounts found</td></tr>
              )}
              {displayAccounts.map(acct => (
                <tr key={acct.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-gray-700 w-40">{acct.account_number}</td>
                  <td className="px-4 py-3 text-gray-700">{acct.account_desc ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-700">{acct.account_group}</td>
                  <td className="px-4 py-3 text-gray-500">{acct.account_sub_group ?? "—"}</td>
                  <td className="px-4 py-3">
                    <span className="px-2 py-0.5 rounded text-xs font-medium bg-indigo-50 text-indigo-700">{acct.cost_element}</span>
                  </td>
                  {canWrite && (
                    <td className="px-4 py-3 text-right">
                      <button onClick={() => { setApiError(null); setEditing(acct); }} className="text-indigo-600 hover:text-indigo-800 text-xs font-medium mr-3">Edit</button>
                      <button onClick={() => { setApiError(null); setDelConfirm(acct); }} className="text-red-500 hover:text-red-700 text-xs font-medium">Delete</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && (
        <Modal title="Add Account Number" onClose={() => setShowAdd(false)}>
          <AccountForm
            onSubmit={handleCreate}
            onClose={() => setShowAdd(false)}
            isPending={create.isPending}
            allAccounts={allAccounts}
          />
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Account Number" onClose={() => setEditing(null)}>
          <AccountForm
            isEdit
            accountNumber={editing.account_number}
            editingId={editing.id}
            initial={{ ...editing }}
            onSubmit={handleUpdate}
            onClose={() => setEditing(null)}
            isPending={update.isPending}
            allAccounts={allAccounts}
          />
        </Modal>
      )}

      {delConfirm && (
        <Modal title="Delete Account Number" onClose={() => setDelConfirm(null)}>
          <p className="text-sm text-gray-700 mb-5">
            Delete account <strong>{delConfirm.account_number}</strong>? This cannot be undone.
          </p>
          <div className="flex justify-end gap-2">
            <button onClick={() => setDelConfirm(null)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Cancel</button>
            <button
              onClick={() => handleDelete(delConfirm.id)}
              disabled={del.isPending}
              className="px-4 py-2 text-sm bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50"
            >
              {del.isPending ? "Deleting…" : "Delete"}
            </button>
          </div>
        </Modal>
      )}
    </div>
  );
}
