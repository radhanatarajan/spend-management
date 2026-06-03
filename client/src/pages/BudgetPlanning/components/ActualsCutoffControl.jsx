import { useNcConfig, useUpdateNcConfig } from "../../../data/budget/hooks";
import { useAuth } from "../../../context/AuthContext";

function getPriorYearMonthOptions(fiscalYear) {
  const priorYear = fiscalYear - 1;
  return Array.from({ length: 12 }, (_, i) => {
    const month = 12 - i; // Dec → Jan
    const key = priorYear * 100 + month;
    const label = new Date(priorYear, month - 1, 1).toLocaleString("en-US", { month: "short", year: "numeric" });
    return { value: key, label };
  });
}

export default function ActualsCutoffControl({ fiscalYear }) {
  const MONTH_OPTIONS = getPriorYearMonthOptions(fiscalYear);
  const { data: config } = useNcConfig(fiscalYear);
  const { mutate: updateConfig, isPending } = useUpdateNcConfig();
  const { user } = useAuth();

  const isAdmin = user?.role === "ADMIN" || user?.role === "BIZ_ADMIN";
  const cutoff = config?.actuals_cutoff_month_key ?? null;

  const cutoffLabel = cutoff
    ? (MONTH_OPTIONS.find((o) => o.value === cutoff)?.label ?? String(cutoff))
    : "Auto-detected";

  function handleChange(e) {
    const value = e.target.value ? Number(e.target.value) : null;
    updateConfig({
      fiscal_year: fiscalYear,
      selected_cost_elements: config?.selected_cost_elements ?? [],
      selected_account_groups: config?.selected_account_groups ?? [],
      selected_account_sub_groups: config?.selected_account_sub_groups ?? [],
      actuals_cutoff_month_key: value,
    });
  }

  if (!isAdmin) {
    return (
      <div className="flex items-center gap-1.5">
        <span className="text-xs text-gray-400 shrink-0">Actuals through:</span>
        <span className="inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-md border bg-gray-50 border-gray-200 text-gray-600">
          <svg className="w-3 h-3 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M5 9V7a5 5 0 0110 0v2a2 2 0 012 2v5a2 2 0 01-2 2H5a2 2 0 01-2-2v-5a2 2 0 012-2zm8-2v2H7V7a3 3 0 016 0z" clipRule="evenodd" />
          </svg>
          {cutoffLabel}
        </span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5">
      <span className="text-xs text-gray-400 shrink-0">Actuals through:</span>
      <select
        value={cutoff ?? ""}
        onChange={handleChange}
        disabled={isPending || !config}
        className="text-sm border border-gray-200 rounded-lg px-2 py-1 focus:outline-none focus:ring-2 focus:ring-indigo-300 text-gray-700 bg-white disabled:opacity-60"
      >
        <option value="">Auto-detected</option>
        {MONTH_OPTIONS.map((o) => (
          <option key={o.value} value={o.value}>{o.label}</option>
        ))}
      </select>
    </div>
  );
}
