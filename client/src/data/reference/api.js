import axios from "axios";

// ── Departments ───────────────────────────────────────────────────────────────

export async function fetchDepartments() {
  const { data } = await axios.get("/api/departments");
  return data;
}

export async function createDepartment(payload) {
  const { data } = await axios.post("/api/departments", payload);
  return data;
}

export async function updateDepartment(code, payload) {
  const { data } = await axios.put(`/api/departments/${code}`, payload);
  return data;
}

export async function deleteDepartment(code) {
  await axios.delete(`/api/departments/${code}`);
}

// ── Account Numbers ───────────────────────────────────────────────────────────

export async function fetchAccounts(filters = {}) {
  const { data } = await axios.get("/api/accounts", { params: filters });
  return data;
}

export async function createAccount(payload) {
  const { data } = await axios.post("/api/accounts", payload);
  return data;
}

export async function updateAccount(id, payload) {
  const { data } = await axios.put(`/api/accounts/${id}`, payload);
  return data;
}

export async function deleteAccount(id) {
  await axios.delete(`/api/accounts/${id}`);
}

// ── Project IDs ───────────────────────────────────────────────────────────────

export async function fetchProjects(filters = {}) {
  const { data } = await axios.get("/api/projects", { params: filters });
  return data;
}

export async function createProject(payload) {
  const { data } = await axios.post("/api/projects", payload);
  return data;
}

export async function updateProject(id, payload) {
  const { data } = await axios.put(`/api/projects/${id}`, payload);
  return data;
}

export async function deleteProject(id) {
  await axios.delete(`/api/projects/${id}`);
}

// ── Activity IDs ──────────────────────────────────────────────────────────────

export async function fetchActivities(filters = {}) {
  const { data } = await axios.get("/api/activities", { params: filters });
  return data;
}

export async function createActivity(payload) {
  const { data } = await axios.post("/api/activities", payload);
  return data;
}

export async function updateActivity(activityId, payload) {
  const { data } = await axios.put(`/api/activities/${activityId}`, payload);
  return data;
}

export async function deleteActivity(activityId) {
  await axios.delete(`/api/activities/${activityId}`);
}
