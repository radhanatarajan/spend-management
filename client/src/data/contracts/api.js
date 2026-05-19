import axios from "axios";

const BASE = "/api/contracts";

export async function fetchContracts() {
  const { data } = await axios.get(BASE);
  return data;
}

export async function fetchContract(id) {
  const { data } = await axios.get(`${BASE}/${id}`);
  return data;
}

export async function createContract(payload) {
  const { data } = await axios.post(BASE, payload);
  return data;
}

export async function updateContract(id, payload) {
  const { data } = await axios.put(`${BASE}/${id}`, payload);
  return data;
}

export async function deleteContract(id) {
  await axios.delete(`${BASE}/${id}`);
}

export async function addContractLine(contractId, payload) {
  const { data } = await axios.post(`${BASE}/${contractId}/lines`, payload);
  return data;
}

export async function updateContractLine(contractId, lineId, payload) {
  const { data } = await axios.put(`${BASE}/${contractId}/lines/${lineId}`, payload);
  return data;
}

export async function deleteContractLine(contractId, lineId) {
  await axios.delete(`${BASE}/${contractId}/lines/${lineId}`);
}

export async function fetchContractReport(fiscalYear) {
  const { data } = await axios.get(`${BASE}/report`, { params: { fiscal_year: fiscalYear } });
  return data;
}
