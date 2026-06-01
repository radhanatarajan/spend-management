import { useNcConfig } from "../../../data/budget/hooks";

export default function CostElementFilter({ fiscalYear }) {
  const { data: config } = useNcConfig(fiscalYear);
  const selected = config?.selected_cost_elements ?? [];

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
