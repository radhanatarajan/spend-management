import { useState, useCallback } from "react";
import { useSpend, useSpendFilterOptions } from "../../data/spend";
import FilterBar from "./FilterBar";
import SpendTable from "./SpendTable";

const DEFAULT_TABLE = { page: 1, page_size: 50, sort_by: "month_key", sort_order: "desc" };

export default function SpendPage() {
  // Active filter selections (slicers) — shared with both table query and filter-options query
  const [activeFilters, setActiveFilters] = useState({});
  // Table-specific state (pagination, sort)
  const [tableState, setTableState] = useState(DEFAULT_TABLE);

  const handleFilterChange = useCallback((newFilters) => {
    setActiveFilters(newFilters);
    setTableState((prev) => ({ ...prev, page: 1 }));
  }, []);

  const handlePageChange = useCallback((page) => {
    setTableState((prev) => ({ ...prev, page }));
  }, []);

  const handleSort = useCallback((sort_by, sort_order) => {
    setTableState((prev) => ({ ...prev, sort_by, sort_order, page: 1 }));
  }, []);

  const queryFilters = { ...activeFilters, ...tableState };

  const { data: filterOptions, isLoading: optionsLoading } = useSpendFilterOptions(activeFilters);
  const { data, isLoading, isError, isFetching } = useSpend(queryFilters);

  return (
    <div className="p-6">
      <div className="max-w-screen-2xl mx-auto">
        <h1 className="text-2xl font-semibold text-gray-900 mb-4">Spend Analytics</h1>
        {optionsLoading ? (
          <div className="bg-white border border-gray-200 rounded-lg p-4 mb-4 animate-pulse h-40" />
        ) : (
          <FilterBar
            options={filterOptions}
            activeFilters={activeFilters}
            onFilterChange={handleFilterChange}
          />
        )}
        <SpendTable
          data={data}
          loading={isLoading}
          fetching={isFetching}
          isError={isError}
          filters={tableState}
          onPageChange={handlePageChange}
          onSort={handleSort}
        />
      </div>
    </div>
  );
}
