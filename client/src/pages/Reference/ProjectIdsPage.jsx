import { useState } from "react";
import { useAuth } from "../../context/AuthContext";
import DropdownSlicer from "../../components/DropdownSlicer";
import {
  useCreateProject, useDeleteProject, useDepartments, useProjects, useUpdateProject,
} from "../../data/reference";

const EMPTY_FORM = { project_name: "", department_codes: [] };

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

function ProjectForm({ initial = EMPTY_FORM, isEdit, projectNumber, onSubmit, onClose, isPending, departments }) {
  const [form, setForm] = useState(initial);
  const set = (k, v) => setForm(p => ({ ...p, [k]: v }));

  function toggleDept(code) {
    setForm(p => ({
      ...p,
      department_codes: p.department_codes.includes(code)
        ? p.department_codes.filter(c => c !== code)
        : [...p.department_codes, code],
    }));
  }

  return (
    <form onSubmit={e => { e.preventDefault(); onSubmit(form); }}>
      <div className="space-y-3">
        {isEdit && projectNumber && (
          <div>
            <label className="block text-xs font-medium text-gray-700 mb-1">Project #</label>
            <div className="px-3 py-2 text-sm font-mono text-gray-600 bg-gray-50 border border-gray-200 rounded-lg">{projectNumber}</div>
          </div>
        )}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">Project Name</label>
          <input
            required
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            value={form.project_name}
            onChange={e => set("project_name", e.target.value)}
            placeholder="e.g. CAPEX-NET-INFRA"
          />
        </div>
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-2">Departments</label>
          <div className="border border-gray-200 rounded-lg divide-y divide-gray-100 max-h-44 overflow-y-auto">
            {departments.map(dept => (
              <label key={dept.department_code} className="flex items-center gap-3 px-3 py-2 cursor-pointer hover:bg-gray-50">
                <input
                  type="checkbox"
                  className="rounded text-indigo-600"
                  checked={form.department_codes.includes(dept.department_code)}
                  onChange={() => toggleDept(dept.department_code)}
                />
                <span className="text-sm text-gray-700">
                  <span className="font-mono text-gray-500 mr-1.5">{dept.department_code}</span>
                  {dept.department_name}
                </span>
              </label>
            ))}
            {departments.length === 0 && (
              <div className="px-3 py-3 text-xs text-gray-400">No departments available</div>
            )}
          </div>
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

export default function ProjectIdsPage() {
  const { user } = useAuth();
  const canWrite = user?.role !== "READ_ONLY";

  const [selectedDepts, setSelectedDepts] = useState([]);

  const { data: projects = [], isLoading, error } = useProjects();
  const { data: departments = [] } = useDepartments();

  const deptOptions = departments.map(d => ({ value: d.department_code, label: `${d.department_code} — ${d.department_name}` }));
  const displayProjects = projects.filter(p =>
    selectedDepts.length === 0 || p.departments.some(d => selectedDepts.includes(d.department_code))
  );

  const create = useCreateProject();
  const update = useUpdateProject();
  const del = useDeleteProject();

  const [showAdd, setShowAdd] = useState(false);
  const [editing, setEditing] = useState(null);
  const [delConfirm, setDelConfirm] = useState(null);
  const [apiError, setApiError] = useState(null);

  function handleCreate(form) {
    setApiError(null);
    create.mutate(form, {
      onSuccess: () => setShowAdd(false),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to create project"),
    });
  }

  function handleUpdate(form) {
    setApiError(null);
    update.mutate({
      id: editing.id,
      project_name: form.project_name,
      department_codes: form.department_codes,
    }, {
      onSuccess: () => setEditing(null),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to update project"),
    });
  }

  function handleDelete(id) {
    setApiError(null);
    del.mutate(id, {
      onSuccess: () => setDelConfirm(null),
      onError: (e) => setApiError(e?.response?.data?.detail ?? "Failed to delete project"),
    });
  }

  return (
    <div className="p-6 max-w-screen-lg mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-semibold text-gray-900">Project IDs</h1>
          <p className="text-sm text-gray-500 mt-0.5">Manage project ID master data</p>
        </div>
        {canWrite && (
          <button
            onClick={() => { setApiError(null); setShowAdd(true); }}
            className="flex items-center gap-1.5 px-4 py-2 bg-indigo-600 text-white text-sm font-medium rounded-lg hover:bg-indigo-700"
          >
            <span className="text-lg leading-none">+</span> Add Project
          </button>
        )}
      </div>

      {/* Filter bar */}
      <div className="flex items-center gap-2 mb-4">
        <DropdownSlicer
          title="Department"
          options={deptOptions}
          selected={selectedDepts}
          onToggle={setSelectedDepts}
          searchable
        />
        {selectedDepts.length > 0 && (
          <button onClick={() => setSelectedDepts([])} className="text-xs text-gray-500 hover:text-gray-800 px-2">Clear</button>
        )}
      </div>

      {apiError && (
        <div className="mb-4 px-4 py-3 bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg">{apiError}</div>
      )}

      {isLoading && <div className="text-sm text-gray-500">Loading…</div>}
      {error && <div className="text-sm text-red-600">Failed to load projects.</div>}

      {!isLoading && !error && (
        <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Project #</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Project Name</th>
                <th className="text-left px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide">Departments</th>
                {canWrite && <th className="px-4 py-3 text-xs font-medium text-gray-500 uppercase tracking-wide text-right">Actions</th>}
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-50">
              {displayProjects.length === 0 && (
                <tr><td colSpan={4} className="px-4 py-8 text-center text-gray-400 text-sm">No projects found</td></tr>
              )}
              {displayProjects.map(proj => (
                <tr key={proj.id} className="hover:bg-gray-50">
                  <td className="px-4 py-3 font-mono text-gray-700">{proj.project_number}</td>
                  <td className="px-4 py-3 text-gray-900">{proj.project_name}</td>
                  <td className="px-4 py-3">
                    {proj.departments.length === 0 ? (
                      <span className="text-gray-400">—</span>
                    ) : (
                      <div className="flex flex-wrap gap-1">
                        {proj.departments.map(d => (
                          <span key={d.department_code} className="px-1.5 py-0.5 rounded text-xs bg-gray-100 text-gray-600">
                            {d.department_name}
                          </span>
                        ))}
                      </div>
                    )}
                  </td>
                  {canWrite && (
                    <td className="px-4 py-3 text-right">
                      <button
                        onClick={() => {
                          setApiError(null);
                          setEditing({
                            ...proj,
                            department_codes: proj.departments.map(d => d.department_code),
                          });
                        }}
                        className="text-indigo-600 hover:text-indigo-800 text-xs font-medium mr-3"
                      >Edit</button>
                      <button
                        onClick={() => { setApiError(null); setDelConfirm(proj); }}
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
        <Modal title="Add Project" onClose={() => setShowAdd(false)}>
          <ProjectForm
            departments={departments}
            onSubmit={handleCreate}
            onClose={() => setShowAdd(false)}
            isPending={create.isPending}
          />
        </Modal>
      )}

      {editing && (
        <Modal title="Edit Project" onClose={() => setEditing(null)}>
          <ProjectForm
            isEdit
            projectNumber={editing.project_number}
            initial={{
              project_name: editing.project_name,
              department_codes: editing.department_codes,
            }}
            departments={departments}
            onSubmit={handleUpdate}
            onClose={() => setEditing(null)}
            isPending={update.isPending}
          />
        </Modal>
      )}

      {delConfirm && (
        <Modal title="Delete Project" onClose={() => setDelConfirm(null)}>
          <p className="text-sm text-gray-700 mb-5">
            Delete project <strong>{delConfirm.project_number} — {delConfirm.project_name}</strong>? This cannot be undone.
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
