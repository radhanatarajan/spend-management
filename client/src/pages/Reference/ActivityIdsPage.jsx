import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import DropdownSlicer from "../../components/DropdownSlicer";
import {
  useAccounts, useActivities, useCreateActivity, useDeleteActivity,
  useDepartments, useProjects, useUpdateActivity,
} from "../../data/reference";

const EXPENSE_TYPES = [
  { value: "opex",  label: "Operational Expenditure (AOPEX)" },
  { value: "capex", label: "Capital Expenditure (ACAPEX)" },
];

const EXPENSE_PREFIX = { opex: "AOPEX", capex: "ACAPEX" };

const EMPTY_FORM = {
  activity_id: "",
  expense_type: "opex",
  activity_id_desc: "",
  department_code: "",
  cost_element_filter: "",
  account_id: "",
  project_id: "",  // stored as string in form, parsed to int on submit
};

function Modal({ title, onClose, children }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg mx-4 p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-gray-900">{title}</h2>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-lg leading-none">&times;</button>
        </div>
        {children}
      </div>
    </div>
  );
}

function ActivityForm({ initial = EMPTY_FORM, isEdit, onSubmit, onClose, isPending }) {
  const [form, setForm] = useState(initial);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const { data: departments = [] } = useDepartments();
  const { data: filteredProjects = [] } = useProjects(
    form.department_code ? { department_code: form.department_code } : undefined
  );
  const { data: allAccounts = [] } = useAccounts();
  const costElements = [...new Set(allAccounts.map(a => a.cost_element))].sort();
  const { data: filteredAccounts = [] } = useAccounts(
    form.cost_element_filter ? { cost_element: form.cost_element_filter } : undefined
  );

  function handleDeptChange(code) {
    setForm(p => ({ ...p, department_code: code, project_id: "" }));
  }

  function handleCostElementChange(ce) {
    setForm(p => ({ ...p, cost_element_filter: ce, account_id: "" }));
  }

  function handleSubmit(e) {
    e.preventDefault();
    const payload = {
      activity_id_desc: form.activity_id_desc || null,
      department_code: form.department_code || null,
      account_id: form.account_id ? parseInt(form.account_id, 10) : null,
      project_id: form.project_id ? parseInt(form.project_id, 10) : null,
    };
    if (isEdit) payload.activity_id = form.activity_id;
    else payload.expense_type = form.expense_type;
    onSubmit(payload);
  }

  const sel = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500";
  const inp = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500";

  return (
    <form onSubmit={handleSubmit}>
      <div className="space-y-3">
        {isEdit && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Activity ID</label>
            <input readOnly className={`${inp} bg-gray-50 text-gray-500 cursor-default`} value={form.activity_id} />
          </div>
        )}
        {!isEdit && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Expense Type *</label>
            <select required className={sel} value={form.expense_type} onChange={e => set("expense_type", e.target.value)}>
              {EXPENSE_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
            <p className="text-xs text-gray-400 mt-1">
              ID will be auto-generated with prefix <span className="font-mono font-medium text-gray-600">{EXPENSE_PREFIX[form.expense_type]}-</span>
            </p>
          </div>
        )}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Description</label>
          <input
            className={inp}
            value={form.activity_id_desc ?? ""}
            onChange={e => set("activity_id_desc", e.target.value)}
            placeholder="Optional"
          />
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Department</label>
          <select className={sel} value={form.department_code ?? ""} onChange={e => handleDeptChange(e.target.value)}>
            <option value="">None</option>
            {departments.map(d => (
              <option key={d.department_code} value={d.department_code}>
                {d.department_code} — {d.department_name}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Project</label>
          <select
            className={sel}
            value={form.project_id ?? ""}
            onChange={e => set("project_id", e.target.value)}
            disabled={!form.department_code}
          >
            <option value="">None</option>
            {filteredProjects.map(p => (
              <option key={p.id} value={p.id}>{p.project_number} — {p.project_name}</option>
            ))}
          </select>
          {!form.department_code && (
            <p className="text-xs text-gray-400 mt-1">Select a department first to filter projects</p>
          )}
        </div>

        <hr className="border-gray-100" />

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Cost Element <span className="text-gray-400 font-normal">(filter accounts)</span></label>
          <select className={sel} value={form.cost_element_filter} onChange={e => handleCostElementChange(e.target.value)}>
            <option value="">All cost elements</option>
            {costElements.map(c => <option key={c} value={c}>{c}</option>)}
          </select>
        </div>

        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Account Number</label>
          <select className={sel} value={form.account_id ?? ""} onChange={e => set("account_id", e.target.value)}>
            <option value="">None</option>
            {filteredAccounts.map(a => (
              <option key={a.id} value={a.id}>
                {a.account_number} — {a.account_group} / {a.cost_element}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex justify-end gap-2 mt-5">
        <button type="button" onClick={onClose} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Cancel</button>
        <button
          type="submit"
          disabled={isPending}
          className="px-4 py-2 text-sm bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50"
        >
          {isPending ? "Saving…" : isEdit ? "Save Changes" : "Create"}
        </button>
      </div>
    </form>
  );
}

export default function ActivityIdsPage() {
  const { user } = useAuth();
  const canWrite = user?.role !== "READ_ONLY";

  const [selectedDepts, setSelectedDepts] = useState([]);
  const [selectedCostElements, setSelectedCostElements] = useState([]);
  const [selectedProjects, setSelectedProjects] = useState([]);

  const { data: activities = [], isLoading, error } = useActivities();
  const { data: departments = [] } = useDepartments();

  const deptOptions = departments.map(d => ({ value: d.department_code, label: `${d.department_code} — ${d.department_name}` }));

  const costElementOptions = [...new Set(activities.map(a => a.cost_element).filter(Boolean))].sort();

  const projectOptions = Object.values(
    activities.reduce((acc, a) => {
      if (a.project_id && !acc[a.project_id]) {
        acc[a.project_id] = { value: a.project_id, label: `${a.project_number} — ${a.project_name}` };
      }
      return acc;
    }, {})
  ).sort((a, b) => a.label.localeCompare(b.label));

  const displayActivities = activities.filter(a => {
    if (selectedDepts.length > 0 && !(a.department_code && selectedDepts.includes(a.department_code))) return false;
    if (selectedCostElements.length > 0 && !(a.cost_element && selectedCostElements.includes(a.cost_element))) return false;
    if (selectedProjects.length > 0 && !(a.project_id && selectedProjects.includes(a.project_id))) return false;
    return true;
  });

  const hasFilters = selectedDepts.length > 0 || selectedCostElements.length > 0 || selectedProjects.length > 0;

  const create = useCreateActivity();
  const update = useUpdateActivity();
  const del = useDeleteActivity();

  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delConfirm, setDelConfirm] = useState(null);
  const [apiError, setApiError] = useState(null);

  function handleCreate(form) {
    setApiError(null);
    create.mutate(form, {
      onSuccess: () => setShowAdd(false),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to create activity"),
    });
  }

  function handleUpdate(form) {
    setApiError(null);
    update.mutate({
      activityId: editing.activity_id,
      activity_id_desc: form.activity_id_desc,
      department_code: form.department_code || null,
      account_id: form.account_id ? parseInt(form.account_id, 10) : null,
      project_id: form.project_id ? parseInt(form.project_id, 10) : null,
    }, {
      onSuccess: () => setEditing(null),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to update activity"),
    });
  }

  function handleDelete(activityId) {
    setApiError(null);
    del.mutate(activityId, {
      onSuccess: () => setDelConfirm(null),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to delete activity"),
    });
  }

  return (
    <div className="p-6 max-w-screen-2xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Activity IDs</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage activity ID master data</p>
        </div>
        {canWrite && (
          <button
            onClick={() => { setApiError(null); setShowAdd(true); }}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700"
          >
            <span className="text-lg leading-none">+</span> Add Activity ID
          </button>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex flex-wrap items-center gap-2 mb-4">
        <DropdownSlicer
          title="Department"
          options={deptOptions}
          selected={selectedDepts}
          onToggle={setSelectedDepts}
          searchable
        />
        <DropdownSlicer
          title="Cost Element"
          options={costElementOptions}
          selected={selectedCostElements}
          onToggle={setSelectedCostElements}
          searchable
        />
        <DropdownSlicer
          title="Project"
          options={projectOptions}
          selected={selectedProjects}
          onToggle={setSelectedProjects}
          searchable
        />
        {hasFilters && (
          <button
            onClick={() => { setSelectedDepts([]); setSelectedCostElements([]); setSelectedProjects([]); }}
            className="text-xs text-gray-500 hover:text-gray-800 px-2"
          >Clear all</button>
        )}
      </div>

      {apiError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">{apiError}</div>
      )}

      {isLoading && <div className="text-sm text-gray-500">Loading…</div>}
      {error && <div className="text-sm text-red-600">Failed to load activity IDs.</div>}

      {!isLoading && !error && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden overflow-x-auto">
          <table className="w-full text-sm min-w-[800px]">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Activity ID</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Description</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Department</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Cost Element</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Account #</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Project</th>
                {canWrite && <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {displayActivities.length === 0 && (
                <tr><td colSpan={7} className="px-4 py-8 text-center text-gray-400 text-sm">No activity IDs found</td></tr>
              )}
              {displayActivities.map(act => (
                <tr key={act.activity_id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-gray-700">{act.activity_id}</td>
                  <td className="px-4 py-3 text-gray-600">{act.activity_id_desc ?? "—"}</td>
                  <td className="px-4 py-3 text-gray-600">{act.department_name ?? "—"}</td>
                  <td className="px-4 py-3">
                    {act.cost_element ? (
                      <span className="px-1.5 py-0.5 rounded text-xs bg-indigo-50 text-indigo-700">{act.cost_element}</span>
                    ) : <span className="text-gray-400">—</span>}
                  </td>
                  <td className="px-4 py-3 font-mono text-gray-600">{act.account_number ?? "—"}</td>
                  <td className="px-4 py-3 font-mono text-gray-600">{act.project_number ?? "—"}</td>
                  {canWrite && (
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => {
                          setApiError(null);
                          setEditing({
                            ...act,
                            cost_element_filter: act.cost_element ?? "",
                            department_code: act.department_code ?? "",
                            account_id: act.account_id?.toString() ?? "",
                            project_id: act.project_id?.toString() ?? "",
                          });
                        }}
                        className="text-indigo-600 hover:text-indigo-800 text-xs font-medium mr-3"
                      >Edit</button>
                      <button
                        onClick={() => { setApiError(null); setDelConfirm(act); }}
                        className="text-red-500 hover:text-red-700 text-xs font-medium"
                      >Delete</button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showAdd && (
        <Modal title="Add Activity ID" onClose={() => setShowAdd(false)}>
          <ActivityForm onSubmit={handleCreate} onClose={() => setShowAdd(false)} isPending={create.isPending} />
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Activity ID" onClose={() => setEditing(null)}>
          <ActivityForm
            isEdit
            initial={editing}
            onSubmit={handleUpdate}
            onClose={() => setEditing(null)}
            isPending={update.isPending}
          />
        </Modal>
      )}

      {delConfirm && (
        <Modal title="Delete Activity ID" onClose={() => setDelConfirm(null)}>
          <p className="text-sm text-gray-700 mb-5">
            Delete activity <strong>{delConfirm.activity_id}</strong>? This cannot be undone.
          </p>
          <div className="flex justify-end gap-2">
            <button onClick={() => setDelConfirm(null)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Cancel</button>
            <button
              onClick={() => handleDelete(delConfirm.activity_id)}
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
