

function fmt(amount) {
  if (amount == null) return "–";
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(amount);
}

function SortIcon({ col, sortBy, sortOrder }) {
  if (col !== sortBy) return <span className="ml-1 text-gray-300">↕</span>;
  return <span className="ml-1 text-indigo-600">{sortOrder === "asc" ? "↑" : "↓"}</span>;
}

function Th({ col, label, filters, onSort, rowSpan, colSpan, className = "" }) {
  const sortable = col != null;
  return (
    <th
      rowSpan={rowSpan}
      colSpan={colSpan}
      onClick={sortable ? () => {
        const next = filters.sort_by === col && filters.sort_order === "asc" ? "desc" : "asc";
        onSort(col, next);
      } : undefined}
      className={`px-2 py-2 text-left text-xs font-semibold text-gray-600 uppercase tracking-wide whitespace-nowrap border-b border-gray-200 bg-gray-50 ${sortable ? "cursor-pointer select-none hover:bg-gray-100" : ""} ${className}`}
    >
      {label}
      {sortable && <SortIcon col={col} sortBy={filters.sort_by} sortOrder={filters.sort_order} />}
    </th>
  );
}

function SkeletonRows({ count = 10, cols = 20 }) {
  return Array.from({ length: count }).map((_, i) => (
    <tr key={i} className="animate-pulse">
      {Array.from({ length: cols }).map((_, j) => (
        <td key={j} className="px-2 py-2">
          <div className="h-3 bg-gray-200 rounded w-full" />
        </td>
      ))}
    </tr>
  ));
}

export default function SpendTable({ data, loading, fetching, isError, filters, onPageChange, onSort }) {
  const rows = data?.items ?? [];
  const total = data?.total ?? 0;
  const page = data?.page ?? filters.page;
  const totalPages = data?.total_pages ?? 1;

  return (
    <div className="bg-white border border-gray-200 rounded-lg overflow-hidden">
      {/* caption bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-200 bg-gray-50">
        <span className="text-sm text-gray-600">
          {total.toLocaleString()} records
        </span>
        {fetching && !loading && (
          <span className="text-xs text-indigo-500 flex items-center gap-1">
            <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24" fill="none">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
            </svg>
            Refreshing
          </span>
        )}
      </div>

      {/* table */}
      <div className="overflow-x-auto">
        <table className="min-w-full text-sm border-collapse">
          <thead>
            {/* row 1: group headers */}
            <tr>
              {/* ungrouped: Month, Expense Type, Co. Code */}
              <Th label="Month" col="month_key" filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="Expense Type" col="expense_type" filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="Co. Code" col="company_code" filters={filters} onSort={onSort} rowSpan={2} />
              {/* Oracle group */}
              <th colSpan={2} className="px-2 py-1 text-center text-xs font-bold text-gray-700 uppercase tracking-wide bg-blue-50 border-b border-blue-200">
                Oracle
              </th>
              {/* Oracle Dept group */}
              <th colSpan={2} className="px-2 py-1 text-center text-xs font-bold text-gray-700 uppercase tracking-wide bg-green-50 border-b border-green-200">
                Oracle Dept
              </th>
              {/* Hierarchy ungrouped */}
              <Th label="Hierarchy" col="oracle_cost_center_hierarchy" filters={filters} onSort={onSort} rowSpan={2} />
              {/* Oracle Account group */}
              <th colSpan={2} className="px-2 py-1 text-center text-xs font-bold text-gray-700 uppercase tracking-wide bg-purple-50 border-b border-purple-200">
                Oracle Account
              </th>
              {/* remaining ungrouped */}
              <Th label="Cost Element" col="oracle_cost_element" filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="Line Desc." col={null} filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="Vendor" col="vendor_name" filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="PO" col="po_recon" filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="PO Number" col={null} filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="PO Line" col={null} filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="Invoice No." col={null} filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="Invoice Line" col={null} filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="JE Source" col="je_source" filters={filters} onSort={onSort} rowSpan={2} />
              <Th label="$" col="amount_usd" filters={filters} onSort={onSort} rowSpan={2} className="text-right" />
            </tr>
            {/* row 2: leaf headers under groups */}
            <tr>
              <Th label="Org" col="oracle_organization" filters={filters} onSort={onSort} className="bg-blue-50" />
              <Th label="Acct. No." col="oracle_account_number" filters={filters} onSort={onSort} className="bg-blue-50" />
              <Th label="Code" col="oracle_department" filters={filters} onSort={onSort} className="bg-green-50" />
              <Th label="Name" col="oracle_department_name" filters={filters} onSort={onSort} className="bg-green-50" />
              <Th label="Group" col="oracle_account_group" filters={filters} onSort={onSort} className="bg-purple-50" />
              <Th label="Sub Group" col="oracle_account_sub_group" filters={filters} onSort={onSort} className="bg-purple-50" />
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {loading ? (
              <SkeletonRows count={10} cols={20} />
            ) : isError ? (
              <tr>
                <td colSpan={20} className="px-4 py-8 text-center text-red-500 text-sm">
                  Failed to load data. Please try again.
                </td>
              </tr>
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={20} className="px-4 py-8 text-center text-gray-400 text-sm">
                  No records match the selected filters.
                </td>
              </tr>
            ) : (
              rows.map((row) => (
                <tr key={row.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.month_label}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.expense_type}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.company_code}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.oracle_organization}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.oracle_account_number}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.oracle_department}</td>
                  <td className="px-2 py-1.5 text-gray-700 max-w-[200px] truncate">{row.oracle_department_name}</td>
                  <td className="px-2 py-1.5 text-gray-700 max-w-[180px] truncate">{row.oracle_cost_center_hierarchy}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.oracle_account_group}</td>
                  <td className="px-2 py-1.5 text-gray-700 max-w-[200px] truncate">{row.oracle_account_sub_group}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.oracle_cost_element}</td>
                  <td className="px-2 py-1.5 text-gray-500 max-w-[300px] truncate">{row.line_desc ?? "–"}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.vendor_name}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700" title={row.po_description ?? ""}>
                    {row.po_recon ?? "–"}
                  </td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.purchase_order_number ?? "–"}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.purchase_order_line_number ?? "–"}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.invoice_number ?? "–"}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.invoice_line_number ?? "–"}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-gray-700">{row.je_source ?? "–"}</td>
                  <td className="px-2 py-1.5 whitespace-nowrap text-right font-mono text-gray-800">{fmt(row.amount_usd)}</td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* pagination */}
      {!loading && !isError && totalPages > 1 && (
        <div className="flex items-center justify-between px-4 py-3 border-t border-gray-200 bg-gray-50">
          <span className="text-sm text-gray-600">
            Page {page} of {totalPages}
          </span>
          <div className="flex gap-1">
            <button
              disabled={page <= 1}
              onClick={() => onPageChange(page - 1)}
              className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              ← Prev
            </button>
            {Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
              let p;
              if (totalPages <= 7) {
                p = i + 1;
              } else if (page <= 4) {
                p = i + 1;
              } else if (page >= totalPages - 3) {
                p = totalPages - 6 + i;
              } else {
                p = page - 3 + i;
              }
              return (
                <button
                  key={p}
                  onClick={() => onPageChange(p)}
                  className={`px-3 py-1 text-sm border rounded ${p === page ? "bg-indigo-600 text-white border-indigo-600" : "border-gray-300 hover:bg-gray-100"}`}
                >
                  {p}
                </button>
              );
            })}
            <button
              disabled={page >= totalPages}
              onClick={() => onPageChange(page + 1)}
              className="px-3 py-1 text-sm border border-gray-300 rounded hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next →
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
