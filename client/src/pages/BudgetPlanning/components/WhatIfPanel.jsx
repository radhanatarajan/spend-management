import { useState, useMemo } from "react";

const fmtFull = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
const fmt = (v) => fmtFull.format(Number(v ?? 0));

const QUARTERS = ["q1", "q2", "q3", "q4"];

export default function WhatIfPanel({ plan }) {
  const [open, setOpen] = useState(false);
  const [approved, setApproved] = useState({});

  const departments = plan?.departments ?? [];
  const totals = plan?.totals;

  const deptsWithAsk = useMemo(
    () => departments.filter((d) => Number(d.additional_ask?.annual) > 0),
    [departments]
  );

  const { approvedBase, approvedWithAsk, totalAsk } = useMemo(() => {
    const approvedBase = totals?.approved_rec?.annual ?? 0;
    let totalAsk = 0;
    let approvedWithAsk = Number(approvedBase);

    for (const dept of deptsWithAsk) {
      const ask = Number(dept.additional_ask?.annual ?? 0);
      totalAsk += ask;
      if (approved[dept.department_name]) {
        approvedWithAsk += ask;
      }
    }

    return { approvedBase, approvedWithAsk, totalAsk };
  }, [deptsWithAsk, approved, totals]);

  const approvedCount = Object.values(approved).filter(Boolean).length;
  const delta = approvedWithAsk - Number(approvedBase);
  const deltaPercent = approvedBase > 0 ? ((delta / Number(approvedBase)) * 100).toFixed(1) : "0.0";

  function toggleAll(val) {
    const next = {};
    deptsWithAsk.forEach((d) => { next[d.department_name] = val; });
    setApproved(next);
  }

  if (!plan) return null;

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      {/* Header toggle */}
      <button
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3.5 text-left hover:bg-gray-50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-gray-800">What-If Analysis</span>
          {approvedCount > 0 && (
            <span className="text-[11px] bg-indigo-100 text-indigo-700 px-2 py-0.5 rounded-full">
              {approvedCount} ask{approvedCount !== 1 ? "s" : ""} approved
            </span>
          )}
        </div>
        <div className="flex items-center gap-4">
          {approvedCount > 0 && (
            <span className="text-xs font-semibold text-indigo-700">
              {fmt(approvedWithAsk)} total (+{deltaPercent}%)
            </span>
          )}
          <span className="text-gray-400 text-xs">{open ? "▲" : "▼"}</span>
        </div>
      </button>

      {open && (
        <div className="border-t border-gray-100 px-4 py-4">
          {deptsWithAsk.length === 0 ? (
            <p className="text-sm text-gray-400 text-center py-4">
              No departments have Additional Ask amounts entered yet.
            </p>
          ) : (
            <>
              {/* Summary bar */}
              <div className="grid grid-cols-3 gap-4 mb-5">
                <div className="bg-gray-50 rounded-lg p-3 text-center">
                  <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">Approved Rec Baseline</div>
                  <div className="text-lg font-semibold text-gray-900">{fmt(approvedBase)}</div>
                </div>
                <div className="bg-amber-50 rounded-lg p-3 text-center">
                  <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">Total Additional Ask Pool</div>
                  <div className="text-lg font-semibold text-amber-700">{fmt(totalAsk)}</div>
                </div>
                <div className={`rounded-lg p-3 text-center ${approvedCount > 0 ? "bg-indigo-50" : "bg-gray-50"}`}>
                  <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1">Projected Total</div>
                  <div className={`text-lg font-semibold ${approvedCount > 0 ? "text-indigo-700" : "text-gray-500"}`}>
                    {fmt(approvedWithAsk)}
                    {delta > 0 && (
                      <span className="text-xs font-normal ml-1 text-indigo-500">+{deltaPercent}%</span>
                    )}
                  </div>
                </div>
              </div>

              {/* Toggle all */}
              <div className="flex justify-between items-center mb-3">
                <span className="text-xs font-medium text-gray-500">Toggle departments to approve their additional ask:</span>
                <div className="flex gap-2">
                  <button onClick={() => toggleAll(true)} className="text-xs text-indigo-600 hover:underline">Approve all</button>
                  <span className="text-gray-300">|</span>
                  <button onClick={() => toggleAll(false)} className="text-xs text-gray-400 hover:underline">Clear all</button>
                </div>
              </div>

              {/* Department toggles */}
              <div className="space-y-2">
                {deptsWithAsk.map((dept) => {
                  const isOn = !!approved[dept.department_name];
                  const askAnnual = Number(dept.additional_ask?.annual ?? 0);
                  return (
                    <div
                      key={dept.department_name}
                      className={`flex items-center justify-between rounded-lg border px-3 py-2.5 transition-colors cursor-pointer ${
                        isOn ? "border-indigo-300 bg-indigo-50" : "border-gray-200 bg-white hover:bg-gray-50"
                      }`}
                      onClick={() => setApproved((p) => ({ ...p, [dept.department_name]: !p[dept.department_name] }))}
                    >
                      <div className="flex items-center gap-2.5">
                        <div className={`w-4 h-4 rounded border-2 flex items-center justify-center transition-colors ${
                          isOn ? "border-indigo-600 bg-indigo-600" : "border-gray-300"
                        }`}>
                          {isOn && <span className="text-white text-[10px] font-bold">✓</span>}
                        </div>
                        <span className="text-xs font-medium text-gray-800">
                          {dept.department_name}
                          {dept.department_code && (
                            <span className="ml-1 font-normal text-gray-400">({dept.department_code})</span>
                          )}
                        </span>
                      </div>
                      <div className="text-right">
                        <div className="text-xs font-semibold text-amber-700">{fmt(askAnnual)}</div>
                        <div className="text-[10px] text-gray-400">annual ask</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
