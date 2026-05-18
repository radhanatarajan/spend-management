import axios from "axios";

const BASE = "/api/spend";

const serializer = { indexes: null };

export async function fetchSpend(params) {
  const { data } = await axios.get(`${BASE}/transactions`, {
    params,
    paramsSerializer: serializer,
  });
  return data;
}

export async function fetchSpendFilterOptions(filters = {}) {
  // Only pass the active filter selections (not sort/page/page_size)
  const { month_keys, expense_types, company_codes, oracle_departments,
          oracle_account_groups, vendors, je_sources } = filters;
  const { data } = await axios.get(`${BASE}/filter-options`, {
    params: { month_keys, expense_types, company_codes, oracle_departments,
              oracle_account_groups, vendors, je_sources },
    paramsSerializer: serializer,
  });
  return data;
}
