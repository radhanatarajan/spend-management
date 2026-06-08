import { useState } from "react";
import { useCreateScenario, useUpdateScenario, useDeleteScenario } from "../../../data/budget/hooks";

export default function ScenarioPanel({ scenarios, selectedId, onSelect, fiscalYear, compact, budgetType = "NON_CONTROLLABLE" }) {
  const [showCreate, setShowCreate] = useState(false);
  const [showRename, setShowRename] = useState(null);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");
  const [copyFrom, setCopyFrom] = useState("");

  const createScenario = useCreateScenario();
  const updateScenario = useUpdateScenario();
  const deleteScenario = useDeleteScenario();

  const selected = scenarios?.find((s) => s.id === selectedId);

  function handleCreate() {
    if (!newName.trim()) return;
    createScenario.mutate(
      {
        name: newName.trim(),
        description: newDesc.trim() || null,
        fiscal_year: fiscalYear,
        budget_type: budgetType,
        copy_from_scenario_id: copyFrom ? Number(copyFrom) : null,
      },
      {
        onSuccess: (data) => {
          onSelect(data.id);
          setShowCreate(false);
          setNewName(""); setNewDesc(""); setCopyFrom("");
        },
      }
    );
  }

  function handleRename() {
    if (!newName.trim() || !showRename) return;
    updateScenario.mutate(
      { id: showRename, name: newName.trim(), description: newDesc.trim() || undefined },
      { onSuccess: () => { setShowRename(null); setNewName(""); setNewDesc(""); } }
    );
  }

  function handleDelete(id) {
    if (!window.confirm("Delete this scenario? This cannot be undone.")) return;
    deleteScenario.mutate(id, {
      onSuccess: () => {
        if (selectedId === id) {
          const baseline = scenarios?.find((s) => s.is_baseline);
          if (baseline) onSelect(baseline.id);
        }
      },
    });
  }

  function openRename(scenario) {
    setShowRename(scenario.id);
    setNewName(scenario.name);
    setNewDesc(scenario.description || "");
  }

  const compactControls = (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400 shrink-0">Scenario:</span>
      <select
        value={selectedId ?? ""}
        onChange={(e) => onSelect(Number(e.target.value))}
        className="text-sm border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-300 text-gray-700 bg-white max-w-[220px]"
      >
        {scenarios?.map((s) => (
          <option key={s.id} value={s.id}>
            {s.name}{s.is_baseline ? " (baseline)" : ""}
          </option>
        ))}
      </select>
      {selected && !selected.is_baseline && (
        <>
          <button
            onClick={() => openRename(selected)}
            className="text-xs text-gray-400 hover:text-indigo-600 transition-colors"
          >
            Rename
          </button>
          <button
            onClick={() => handleDelete(selected.id)}
            className="text-xs text-red-400 hover:text-red-600 transition-colors"
          >
            Delete
          </button>
        </>
      )}
      <button
        onClick={() => { setShowCreate(true); setNewName(""); setNewDesc(""); setCopyFrom(""); }}
        className="text-xs px-2.5 py-1 rounded-md border border-dashed border-indigo-300 text-indigo-600 hover:bg-indigo-50 transition-colors whitespace-nowrap"
      >
        + New
      </button>
    </div>
  );

  const fullControls = (
    <div className="flex items-center justify-between gap-3 flex-wrap">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-gray-400 shrink-0">Scenario:</span>
        <div className="flex items-center gap-1.5 flex-wrap">
          {scenarios?.map((s) => (
            <button
              key={s.id}
              onClick={() => onSelect(s.id)}
              className={`text-xs px-3 py-1.5 rounded-md border transition-colors ${
                s.id === selectedId
                  ? "bg-indigo-600 border-indigo-600 text-white"
                  : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
              }`}
            >
              {s.name}
              {s.is_baseline && (
                <span className="ml-1.5 text-[10px] opacity-70">baseline</span>
              )}
            </button>
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {selected && !selected.is_baseline && (
          <>
            <button onClick={() => openRename(selected)} className="text-xs text-gray-500 hover:text-indigo-600 transition-colors">Rename</button>
            <button onClick={() => handleDelete(selected.id)} className="text-xs text-red-400 hover:text-red-600 transition-colors">Delete</button>
          </>
        )}
        <button
          onClick={() => { setShowCreate(true); setNewName(""); setNewDesc(""); setCopyFrom(""); }}
          className="text-xs px-3 py-1.5 rounded-md border border-dashed border-indigo-300 text-indigo-600 hover:bg-indigo-50 transition-colors"
        >
          + New Scenario
        </button>
      </div>
    </div>
  );

  return (
    <>
      {compact ? compactControls : (
        <div className="bg-white border border-gray-200 rounded-xl p-4">
          {fullControls}
        </div>
      )}

      {/* Create modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Create Scenario</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Name</label>
                <input
                  autoFocus
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  placeholder="e.g. Aggressive FY2027"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleCreate()}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Description (optional)</label>
                <input
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  placeholder="Brief description"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Copy amounts from (optional)</label>
                <select
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  value={copyFrom}
                  onChange={(e) => setCopyFrom(e.target.value)}
                >
                  <option value="">— Start blank —</option>
                  {scenarios?.map((s) => (
                    <option key={s.id} value={s.id}>{s.name}</option>
                  ))}
                </select>
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => setShowCreate(false)}
                className="text-sm px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={!newName.trim() || createScenario.isPending}
                className="text-sm px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                Create
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Rename modal */}
      {showRename && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
          <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md mx-4">
            <h3 className="text-sm font-semibold text-gray-900 mb-4">Rename Scenario</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">Name</label>
                <input
                  autoFocus
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleRename()}
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">Description</label>
                <input
                  className="w-full text-sm border border-gray-200 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-300"
                  value={newDesc}
                  onChange={(e) => setNewDesc(e.target.value)}
                />
              </div>
            </div>
            <div className="flex justify-end gap-2 mt-5">
              <button
                onClick={() => setShowRename(null)}
                className="text-sm px-4 py-2 rounded-lg border border-gray-200 text-gray-600 hover:bg-gray-50"
              >
                Cancel
              </button>
              <button
                onClick={handleRename}
                disabled={!newName.trim() || updateScenario.isPending}
                className="text-sm px-4 py-2 rounded-lg bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50"
              >
                Save
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
