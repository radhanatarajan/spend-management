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
          oracle_account_groups, vendors, je_sources, activity_ids } = filters;
  const { data } = await axios.get(`${BASE}/filter-options`, {
    params: { month_keys, expense_types, company_codes, oracle_departments,
              oracle_account_groups, vendors, je_sources, activity_ids },
    paramsSerializer: serializer,
  });
  return data;
}

export async function fetchSpendSummary(filters = {}) {
  const { month_keys, expense_types, company_codes, oracle_departments,
          oracle_account_groups, vendors, je_sources, activity_ids } = filters;
  const { data } = await axios.get(`${BASE}/summary`, {
    params: { month_keys, expense_types, company_codes, oracle_departments,
              oracle_account_groups, vendors, je_sources, activity_ids },
    paramsSerializer: serializer,
  });
  return data;
}

export async function chatWithGapsAgent(messages) {
  const { data } = await axios.post(`${BASE}/reports/gaps-agent/chat`, { messages });
  return data;
}

export async function downloadSpendCsv(filters = {}) {
  const { month_keys, expense_types, company_codes, oracle_departments,
          oracle_account_groups, vendors, je_sources, activity_ids } = filters;
  const resp = await axios.get(`${BASE}/export`, {
    params: { month_keys, expense_types, company_codes, oracle_departments,
              oracle_account_groups, vendors, je_sources, activity_ids },
    paramsSerializer: serializer,
    responseType: "blob",
  });
  const url = URL.createObjectURL(resp.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `spend_export_${new Date().toISOString().slice(0, 10)}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}
