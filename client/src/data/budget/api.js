import axios from "axios";

const BASE = "/api/budget";

export async function fetchCostElements() {
  const { data } = await axios.get(`${BASE}/cost-elements`);
  return data;
}

export async function fetchNcConfig(fiscalYear) {
  const { data } = await axios.get(`${BASE}/config`, { params: { fiscal_year: fiscalYear } });
  return data;
}

export async function updateNcConfig(payload) {
  const { data } = await axios.put(`${BASE}/config`, payload);
  return data;
}

export async function fetchScenarios(fiscalYear, budgetType) {
  const { data } = await axios.get(`${BASE}/scenarios`, {
    params: { fiscal_year: fiscalYear, budget_type: budgetType },
  });
  return data;
}

export async function createScenario(payload) {
  const { data } = await axios.post(`${BASE}/scenarios`, payload);
  return data;
}

export async function updateScenario(id, payload) {
  const { data } = await axios.put(`${BASE}/scenarios/${id}`, payload);
  return data;
}

export async function deleteScenario(id) {
  await axios.delete(`${BASE}/scenarios/${id}`);
}

export async function fetchNonControllablePlan(fiscalYear, scenarioId) {
  const { data } = await axios.get(`${BASE}/non-controllable`, {
    params: { fiscal_year: fiscalYear, scenario_id: scenarioId },
  });
  return data;
}

export async function upsertEntry(payload) {
  const { data } = await axios.put(`${BASE}/entries`, payload);
  return data;
}

export async function deleteEntry(id) {
  await axios.delete(`${BASE}/entries/${id}`);
}

export async function fetchScenarioComparison(fiscalYear, scenarioAId, scenarioBId) {
  const { data } = await axios.get(`${BASE}/compare`, {
    params: { fiscal_year: fiscalYear, scenario_a_id: scenarioAId, scenario_b_id: scenarioBId },
  });
  return data;
}

export async function updateEntryStatus(id, status) {
  const { data } = await axios.patch(`${BASE}/entries/${id}/status`, { status });
  return data;
}

export async function fetchScenarioAudit(scenarioId) {
  const { data } = await axios.get(`${BASE}/scenarios/${scenarioId}/audit`);
  return data;
}

export async function fetchBudgetAuditReport(fiscalYear) {
  const { data } = await axios.get(`${BASE}/reports/audit`, { params: { fiscal_year: fiscalYear } });
  return data;
}
