import DropdownSlicer from "../../components/DropdownSlicer";

export default function FilterBar({ options, activeFilters, onFilterChange }) {
  function set(key) {
    return (val) => onFilterChange({ ...activeFilters, [key]: val });
  }

  const monthOptions = (options?.months ?? []).map((m) => ({
    value: String(m.month_key),
    label: m.month_label,
  }));

  const deptOptions = (options?.oracle_departments ?? []).map((d) => ({
    value: d.oracle_department,
    label: `${d.oracle_department} – ${d.oracle_department_name}`,
  }));

  return (
    <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4">
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        <DropdownSlicer
          title="Month"
          options={monthOptions}
          selected={activeFilters.month_keys ?? []}
          onToggle={set("month_keys")}
        />
        <DropdownSlicer
          title="Expense Type"
          options={options?.expense_types ?? []}
          selected={activeFilters.expense_types ?? []}
          onToggle={set("expense_types")}
        />
        <DropdownSlicer
          title="Co. Code"
          options={options?.company_codes ?? []}
          selected={activeFilters.company_codes ?? []}
          onToggle={set("company_codes")}
        />
        <DropdownSlicer
          title="Oracle Dept"
          options={deptOptions}
          selected={activeFilters.oracle_departments ?? []}
          onToggle={set("oracle_departments")}
        />
        <DropdownSlicer
          title="Acct. Group"
          options={options?.oracle_account_groups ?? []}
          selected={activeFilters.oracle_account_groups ?? []}
          onToggle={set("oracle_account_groups")}
        />
        <DropdownSlicer
          title="Vendor"
          options={options?.vendors ?? []}
          selected={activeFilters.vendors ?? []}
          onToggle={set("vendors")}
        />
        <DropdownSlicer
          title="JE Source"
          options={options?.je_sources ?? []}
          selected={activeFilters.je_sources ?? []}
          onToggle={set("je_sources")}
        />
      </div>
    </div>
  );
}
