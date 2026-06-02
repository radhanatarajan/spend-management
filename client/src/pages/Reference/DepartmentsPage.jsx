import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import {
  useCreateDepartment, useDeleteDepartment, useDepartments, useUpdateDepartment,
} from "../../data/reference";

const EMPTY_FORM = { department_code: "", department_name: "" };

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

function DeptForm({ initial = EMPTY_FORM, isEdit, onSubmit, onClose, isPending, existingCodes = [] }) {
  const [form, setForm] = useState(initial);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  const isDuplicate = !isEdit && form.department_code.trim() !== "" &&
    existingCodes.includes(form.department_code.trim());

  return (
    <form onSubmit={e => { e.preventDefault(); if (!isDuplicate) onSubmit(form); }}>
      <div className="space-y-3">
        {!isEdit && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Department Code</label>
            <input
              required
              className={`w-full border rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 ${isDuplicate ? "border-red-400 focus:ring-red-400" : "border-gray-300 focus:ring-indigo-500"}`}
              value={form.department_code}
              onChange={e => set("department_code", e.target.value)}
              placeholder="e.g. 1900"
            />
            {isDuplicate && (
              <p className="text-xs text-red-600 mt-1">This department code already exists.</p>
            )}
          </div>
        )}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Department Name</label>
          <input
            required
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={form.department_name}
            onChange={e => set("department_name", e.target.value)}
            placeholder="e.g. DevRel"
          />
        </div>
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

export default function DepartmentsPage() {
  const { user } = useAuth();
  const canWrite = user?.role !== "READ_ONLY";

  const { data: departments = [], isLoading, error } = useDepartments();
  const existingCodes = departments.map(d => d.department_code);
  const create = useCreateDepartment();
  const update = useUpdateDepartment();
  const del = useDeleteDepartment();

  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delConfirm, setDelConfirm] = useState(null);
  const [apiError, setApiError] = useState(null);

  function handleCreate(form) {
    setApiError(null);
    create.mutate(form, {
      onSuccess: () => setShowAdd(false),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to create department"),
    });
  }

  function handleUpdate(form) {
    setApiError(null);
    update.mutate({ code: editing.department_code, department_name: form.department_name }, {
      onSuccess: () => setEditing(null),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to update department"),
    });
  }

  function handleDelete(code) {
    setApiError(null);
    del.mutate(code, {
      onSuccess: () => setDelConfirm(null),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to delete department"),
    });
  }

  return (
    <div className="p-6 max-w-screen-lg mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Departments</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage department master data</p>
        </div>
        {canWrite && (
          <button
            onClick={() => { setApiError(null); setShowAdd(true); }}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700"
          >
            <span className="text-lg leading-none">+</span> Add Department
          </button>
        )}
      </div>

      {apiError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">{apiError}</div>
      )}

      {isLoading && <div className="text-sm text-gray-500">Loading…</div>}
      {error && <div className="text-sm text-red-600">Failed to load departments.</div>}

      {!isLoading && !error && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Code</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Name</th>
                {canWrite && <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {departments.length === 0 && (
                <tr><td colSpan={3} className="px-4 py-8 text-center text-gray-400 text-sm">No departments yet</td></tr>
              )}
              {departments.map(dept => (
                <tr key={dept.department_code} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-gray-700">{dept.department_code}</td>
                  <td className="px-4 py-3 text-gray-900">{dept.department_name}</td>
                  {canWrite && (
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => { setApiError(null); setEditing(dept); }}
                        className="text-indigo-600 hover:text-indigo-800 text-xs font-medium mr-3"
                      >Edit</button>
                      <button
                        onClick={() => { setApiError(null); setDelConfirm(dept); }}
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
        <Modal title="Add Department" onClose={() => setShowAdd(false)}>
          <DeptForm onSubmit={handleCreate} onClose={() => setShowAdd(false)} isPending={create.isPending} existingCodes={existingCodes} />
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Department" onClose={() => setEditing(null)}>
          <DeptForm
            isEdit
            initial={{ department_code: editing.department_code, department_name: editing.department_name }}
            onSubmit={handleUpdate}
            onClose={() => setEditing(null)}
            isPending={update.isPending}
          />
        </Modal>
      )}

      {delConfirm && (
        <Modal title="Delete Department" onClose={() => setDelConfirm(null)}>
          <p className="text-sm text-gray-700 mb-5">
            Delete <strong>{delConfirm.department_code} — {delConfirm.department_name}</strong>? This cannot be undone.
          </p>
          <div className="flex justify-end gap-2">
            <button onClick={() => setDelConfirm(null)} className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900">Cancel</button>
            <button
              onClick={() => handleDelete(delConfirm.department_code)}
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
