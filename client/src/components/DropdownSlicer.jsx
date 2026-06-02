import { useState, useRef, useEffect } from "react";

export default function DropdownSlicer({ title, options, selected, onToggle, searchable = false }) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const searchRef = useRef(null);
  const ref = useRef(null);

  useEffect(() => {
    function onClickOutside(e) {
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false);
        setQuery("");
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, []);

  useEffect(() => {
    if (open && searchable && searchRef.current) searchRef.current.focus();
  }, [open, searchable]);

  const allSelected = selected.length === 0;
  const count = selected.length;

  const visibleOptions = searchable && query.trim()
    ? options.filter((opt) => {
        const label = typeof opt === "object" ? opt.label : opt;
        return label.toLowerCase().includes(query.toLowerCase());
      })
    : options;

  function toggleAll() {
    onToggle([]);
  }

  function toggleValue(val) {
    if (selected.includes(val)) {
      onToggle(selected.filter((v) => v !== val));
    } else {
      onToggle([...selected, val]);
    }
  }

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => { setOpen((o) => { if (o) setQuery(""); return !o; }); }}
        className={`w-full flex items-center justify-between gap-2 px-3 py-2 text-sm border rounded-lg bg-white transition-colors ${
          open
            ? "border-indigo-400 ring-2 ring-indigo-100"
            : count > 0
            ? "border-indigo-400 bg-indigo-50"
            : "border-gray-300 hover:border-gray-400"
        }`}
      >
        <span className="flex items-center gap-1.5 min-w-0">
          <span className="text-xs font-semibold text-gray-500 uppercase tracking-wide truncate">
            {title}
          </span>
          {count > 0 && (
            <span className="inline-flex items-center justify-center px-1.5 py-0.5 rounded-full text-xs font-medium bg-indigo-600 text-white leading-none">
              {count}
            </span>
          )}
        </span>
        <svg
          className={`w-4 h-4 text-gray-400 shrink-0 transition-transform ${open ? "rotate-180" : ""}`}
          fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
        >
          <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
        </svg>
      </button>

      {open && (
        <div className="absolute z-50 mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg overflow-hidden">
          {searchable && (
            <div className="px-2 py-2 border-b border-gray-100">
              <input
                ref={searchRef}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search..."
                className="w-full px-2 py-1 text-sm border border-gray-300 rounded focus:outline-none focus:border-indigo-400 focus:ring-1 focus:ring-indigo-200"
              />
            </div>
          )}

          {!query && (
            <label className="flex items-center gap-2 px-3 py-2 hover:bg-gray-50 cursor-pointer border-b border-gray-100">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={toggleAll}
                className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
              />
              <span className="text-sm font-medium text-gray-700">All</span>
            </label>
          )}

          <div className="max-h-52 overflow-y-auto">
            {visibleOptions.length === 0 && (
              <p className="px-3 py-3 text-sm text-gray-400">No matches</p>
            )}
            {visibleOptions.map((opt) => {
              const val = typeof opt === "object" ? opt.value : opt;
              const label = typeof opt === "object" ? opt.label : opt;
              const checked = selected.includes(val);
              return (
                <label
                  key={val}
                  className="flex items-center gap-2 px-3 py-1.5 hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => toggleValue(val)}
                    className="rounded border-gray-300 text-indigo-600 focus:ring-indigo-500"
                  />
                  <span className="text-sm text-gray-700 truncate" title={label}>{label}</span>
                </label>
              );
            })}
          </div>

          {count > 0 && (
            <div className="border-t border-gray-100 px-3 py-2">
              <button
                onClick={toggleAll}
                className="text-xs text-indigo-600 hover:text-indigo-800 font-medium"
              >
                Clear selection
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
