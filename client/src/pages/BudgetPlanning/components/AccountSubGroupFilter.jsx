import { useNcConfig, useUpdateNcConfig, useAccountSubGroups } from "../../../data/budget/hooks";
import { useAuth } from "../../../context/AuthContext";
import DropdownSlicer from "../../../components/DropdownSlicer";

export default function AccountSubGroupFilter({ fiscalYear }) {
  const { data: config } = useNcConfig(fiscalYear);
  const { data: available = [] } = useAccountSubGroups();
  const { mutate: updateConfig, isPending } = useUpdateNcConfig();
  const { user } = useAuth();

  const isAdmin = user?.role === "ADMIN" || user?.role === "BIZ_ADMIN";
  const selected = config?.selected_account_sub_groups ?? [];

  function handleToggle(newSelected) {
    updateConfig({
      fiscal_year: fiscalYear,
      selected_cost_elements: config?.selected_cost_elements ?? [],
      selected_account_groups: config?.selected_account_groups ?? [],
      selected_account_sub_groups: newSelected,
      actuals_cutoff_month_key: config?.actuals_cutoff_month_key ?? null,
    });
  }

  if (!isAdmin) {
    return (
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs text-gray-400 shrink-0">Account Sub Group:</span>
        {selected.length === 0 ? (
          <span className="text-xs text-gray-400 italic">All</span>
        ) : (
          selected.map((g) => (
            <span
              key={g}
              className="text-xs px-2.5 py-1 rounded-md border bg-sky-50 border-sky-200 text-sky-700 whitespace-nowrap"
            >
              {g}
            </span>
          ))
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-xs text-gray-400 shrink-0">Account Sub Group:</span>
      <div className={`w-36 ${isPending ? "opacity-60 pointer-events-none" : ""}`}>
        <DropdownSlicer
          title="Account Sub Group"
          options={available}
          selected={selected}
          onToggle={handleToggle}
          searchable
        />
      </div>
    </div>
  );
}
