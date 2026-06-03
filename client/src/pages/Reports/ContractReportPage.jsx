import { useState, useMemo } from "react";
import { useContractReport } from "../../data/contracts";
import DropdownSlicer from "../../components/DropdownSlicer";

// ── Helpers ───────────────────────────────────────────────────────────────────

const fmtFull = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", minimumFractionDigits: 0, maximumFractionDigits: 0 });
const fmtCompact = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", notation: "compact", maximumFractionDigits: 1 });

const fmtUSD = (v) => fmtFull.format(Number(v ?? 0));
const fmtK   = (v) => fmtCompact.format(Number(v ?? 0));

function currentFiscalYear() {
  return new Date().getFullYear();
}

const STATUS_CHIP = {
  active:    "bg-green-100 text-green-700",
  expired:   "bg-gray-100 text-gray-500",
  cancelled: "bg-red-100 text-red-600",
  pending:   "bg-yellow-100 text-yellow-700",
};

// ── Pill slicer ───────────────────────────────────────────────────────────────

function Pill({ active, onClick, children }) {
  return (
    <button
      onClick={onClick}
      className={`text-xs px-2.5 py-1 rounded-md border transition-colors whitespace-nowrap ${
        active
          ? "bg-indigo-600 border-indigo-600 text-white"
          : "bg-white border-gray-200 text-gray-600 hover:bg-gray-50"
      }`}
    >
      {children}
    </button>
  );
}

// ── KPI card ──────────────────────────────────────────────────────────────────

function KpiCard({ label, value, sub }) {
  return (
    <div className="bg-white border border-gray-100 rounded-xl p-4">
      <div className="text-[10px] text-gray-400 uppercase tracking-wide mb-1.5">{label}</div>
      <div className="text-xl font-semibold text-gray-900 truncate">{value}</div>
      {sub && <div className="text-[10px] text-gray-400 mt-0.5">{sub}</div>}
    </div>
  );
}

// ── Monthly table ─────────────────────────────────────────────────────────────

function MonthlyTable({ report, rows }) {
  const { month_keys, month_labels } = report;

  // Recompute monthly totals based on filtered rows (must be before early return — hooks rules)
  const filteredTotals = useMemo(() => {
    const t = {};
    for (const key of month_keys) {
      t[key] = rows.reduce((sum, r) => sum + Number(r.monthly_amounts[key] ?? 0), 0);
    }
    return t;
  }, [rows, month_keys]);

  const filteredGrandTotal = rows.reduce((s, r) => s + Number(r.fiscal_year_total), 0);

  if (!rows.length) {
    return (
      <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400">
        No contracts with coverage in this fiscal year.
      </div>
    );
  }

  return (
    <div className="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm">
      <div className="overflow-x-auto">
        <table className="w-full text-xs border-collapse">
          <thead>
            {/* Month header */}
            <tr className="bg-gray-50 border-b border-gray-200">
              <th className="sticky left-0 z-10 bg-gray-50 px-4 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[160px]">
                Vendor
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[110px]">
                Department
              </th>
              <th className="px-3 py-3 text-left font-medium text-gray-500 uppercase tracking-wide min-w-[100px]">
                Account
              </th>
              {month_labels.map((lbl, i) => (
                <th key={month_keys[i]} className="px-3 py-3 text-right font-medium text-gray-500 uppercase tracking-wide min-w-[88px] whitespace-nowrap">
                  {lbl}
                </th>
              ))}
              <th className="px-3 py-3 text-right font-semibold text-gray-700 uppercase tracking-wide min-w-[100px] bg-indigo-50">
                FY Total
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {rows.map((row) => (
              <tr key={row.id} className="hover:bg-gray-50 group">
                <td className="sticky left-0 z-10 bg-white group-hover:bg-gray-50 px-4 py-2.5">
                  <div className="flex items-center gap-1.5 leading-tight">
                    <span className="font-medium text-gray-900">{row.vendor_name}</span>
                    {row.is_multi_year && (
                      <span className="text-[9px] font-semibold uppercase tracking-wide px-1 py-0.5 rounded bg-indigo-50 text-indigo-600">Multi-yr</span>
                    )}
                  </div>
                  <div className="text-gray-400 text-[10px] mt-0.5">{row.purchase_order_number} · {row.num_lines} line{row.num_lines !== 1 ? "s" : ""}</div>
                  <span className={`inline-block mt-0.5 px-1.5 py-0.5 rounded text-[10px] font-medium capitalize ${STATUS_CHIP[row.status] ?? "bg-gray-100 text-gray-500"}`}>
                    {row.status}
                  </span>
                </td>
                <td className="px-3 py-2.5 text-gray-600 align-top">{row.oracle_department_name}</td>
                <td className="px-3 py-2.5 text-gray-500 font-mono align-top">{row.oracle_account_number}</td>
                {month_keys.map((key) => {
                  const amt = row.monthly_amounts[key];
                  const assumed = row.monthly_assumed[key];
                  return (
                    <td key={key} title={assumed ? "100% renewal assumption" : undefined}
                      className={`px-3 py-2.5 text-right font-mono align-top ${
                        amt == null ? "text-gray-200"
                        : assumed   ? "text-amber-500 italic"
                                    : "text-gray-800"
                      }`}>
                      {amt != null ? (assumed ? `~${fmtK(amt)}` : fmtK(amt)) : "–"}
                    </td>
                  );
                })}
                <td className="px-3 py-2.5 text-right font-mono font-semibold text-indigo-700 bg-indigo-50 align-top">
                  {fmtK(row.fiscal_year_total)}
                </td>
              </tr>
            ))}
          </tbody>
          <tfoot>
            <tr className="bg-gray-50 border-t-2 border-gray-200 font-semibold">
              <td className="sticky left-0 z-10 bg-gray-50 px-4 py-2.5 text-gray-700">Total</td>
              <td className="px-3 py-2.5" colSpan={2} />
              {month_keys.map((key) => (
                <td key={key} className="px-3 py-2.5 text-right font-mono text-gray-900">
                  {filteredTotals[key] > 0 ? fmtK(filteredTotals[key]) : "–"}
                </td>
              ))}
              <td className="px-3 py-2.5 text-right font-mono font-bold text-indigo-700 bg-indigo-50">
                {fmtK(filteredGrandTotal)}
              </td>
            </tr>
          </tfoot>
        </table>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function ContractReportPage() {
  const [fiscalYear, setFiscalYear] = useState(currentFiscalYear);
  const [selVendors,          setSelVendors]          = useState([]);
  const [selDepts,            setSelDepts]            = useState([]);
  const [selStatus,           setSelStatus]           = useState([]);
  const [selAccountGroups,    setSelAccountGroups]    = useState([]);
  const [selAccountSubGroups, setSelAccountSubGroups] = useState([]);
  const [selCostElements,     setSelCostElements]     = useState([]);

  const { data: report, isLoading, isError } = useContractReport(fiscalYear);

  // Once data loads, seed the FY selector with available years
  const availableFYs = report?.available_fiscal_years ?? [];

  // Client-side filtering
  const filteredRows = useMemo(() => {
    if (!report) return [];
    return report.rows.filter((r) => {
      if (selVendors.length          && !selVendors.includes(r.vendor_name))              return false;
      if (selDepts.length            && !selDepts.includes(r.oracle_department_name))      return false;
      if (selStatus.length           && !selStatus.includes(r.status))                    return false;
      if (selAccountGroups.length    && !selAccountGroups.includes(r.account_group))      return false;
      if (selAccountSubGroups.length && !selAccountSubGroups.includes(r.account_sub_group)) return false;
      if (selCostElements.length     && !selCostElements.includes(r.cost_element))        return false;
      return true;
    });
  }, [report, selVendors, selDepts, selStatus, selAccountGroups, selAccountSubGroups, selCostElements]);

  // KPIs
  const numContracts   = filteredRows.length;
  const numVendors     = new Set(filteredRows.map((r) => r.vendor_name)).size;
  const grandTotal     = filteredRows.reduce((s, r) => s + Number(r.fiscal_year_total), 0);
  const assumedTotal   = filteredRows.reduce((s, r) => s + Number(r.assumed_total), 0);
  return (
    <div className="p-6 space-y-5">

      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-base font-semibold text-gray-900">Contract Report</h1>
          <p className="text-xs text-gray-400 mt-0.5">
            All contracts · {report?.period_label ?? "…"} · monthly breakout
          </p>
        </div>

        {/* FY Picker */}
        <div className="flex items-center gap-1">
          {(availableFYs.length > 0 ? availableFYs : [fiscalYear]).map((fy) => (
            <Pill key={fy} active={fiscalYear === fy} onClick={() => setFiscalYear(fy)}>
              FY{fy}
            </Pill>
          ))}
        </div>
      </div>

      {/* Slicers */}
      {report && (
        <div className="bg-white border border-gray-100 rounded-xl px-4 py-3">
          <div className="grid grid-cols-3 gap-3">
            <DropdownSlicer
              title="Vendor"
              options={report.filter_options.vendors}
              selected={selVendors}
              onToggle={setSelVendors}
              searchable
            />
            <DropdownSlicer
              title="Department"
              options={report.filter_options.departments}
              selected={selDepts}
              onToggle={setSelDepts}
              searchable
            />
            <DropdownSlicer
              title="Status"
              options={report.filter_options.statuses}
              selected={selStatus}
              onToggle={setSelStatus}
            />
            <DropdownSlicer
              title="Account Group"
              options={report.filter_options.account_groups}
              selected={selAccountGroups}
              onToggle={setSelAccountGroups}
              searchable
            />
            <DropdownSlicer
              title="Account Sub Group"
              options={report.filter_options.account_sub_groups}
              selected={selAccountSubGroups}
              onToggle={setSelAccountSubGroups}
              searchable
            />
            <DropdownSlicer
              title="Cost Element"
              options={report.filter_options.cost_elements}
              selected={selCostElements}
              onToggle={setSelCostElements}
              searchable
            />
          </div>
        </div>
      )}

      {/* KPI cards */}
      <div className="grid grid-cols-4 gap-3">
        <KpiCard label="Contracts"        value={numContracts} sub={`${filteredRows.filter(r => r.is_multi_year).length} multi-year`} />
        <KpiCard label="Vendors"          value={numVendors} />
        <KpiCard label="FY Total Value"   value={fmtK(grandTotal)} sub={fmtUSD(grandTotal)} />
        <KpiCard label="Assumed (renewal)" value={fmtK(assumedTotal)} sub={assumedTotal > 0 ? "~100% renewal rate" : "all lines signed"} />
      </div>

      {/* Table */}
      {isLoading ? (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-gray-400 animate-pulse">
          Loading contract report…
        </div>
      ) : isError ? (
        <div className="bg-white border border-gray-200 rounded-xl p-8 text-center text-sm text-red-500">
          Failed to load report. Make sure multi-year contracts exist.
        </div>
      ) : (
        <MonthlyTable report={report} rows={filteredRows} />
      )}

    </div>
  );
}
