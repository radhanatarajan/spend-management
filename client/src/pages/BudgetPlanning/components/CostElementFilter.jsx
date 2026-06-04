import { useNcConfig, useUpdateNcConfig, useCostElements } from "../../../data/budget/hooks";
import { useAuth } from "../../../context/AuthContext";
import DropdownSlicer from "../../../components/DropdownSlicer";

export default function CostElementFilter({ fiscalYear }) {
  const { data: config } = useNcConfig(fiscalYear);
  const { data: available = [] } = useCostElements();
  const { mutate: updateConfig, isPending } = useUpdateNcConfig();
  const { user } = useAuth();

  const isAdmin = user?.role === "ADMIN" || user?.role === "BIZ_ADMIN";
  const selected = config?.selected_cost_elements ?? [];

  function handleToggle(newSelected) {
    updateConfig({
      fiscal_year: fiscalYear,
      selected_cost_elements: newSelected,
      selected_account_groups: config?.selected_account_groups ?? [],
      selected_account_sub_groups: config?.selected_account_sub_groups ?? [],
      actuals_cutoff_month_key: config?.actuals_cutoff_month_key ?? null,
    });
  }

  if (!isAdmin) {
    return (
      <div className="flex items-center gap-1.5 flex-wrap">
        <span className="text-xs text-gray-400 shrink-0">Cost Elements:</span>
        {selected.length === 0 ? (
          <span className="text-xs text-gray-400 italic">None configured</span>
        ) : (
          selected.map((el) => (
            <span
              key={el}
              className="text-xs px-2.5 py-1 rounded-md border bg-indigo-50 border-indigo-200 text-indigo-700 whitespace-nowrap"
            >
              {el}
            </span>
          ))
        )}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-1.5 flex-wrap">
      <span className="text-xs text-gray-400 shrink-0">Cost Elements:</span>
      <div className={`w-36 ${isPending ? "opacity-60 pointer-events-none" : ""}`}>
        <DropdownSlicer
          title="Cost Element"
          options={available}
          selected={selected}
          onToggle={handleToggle}
          searchable
        />
      </div>
    </div>
  );
}
