import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createAccount, createActivity, createDepartment, createProject,
  deleteAccount, deleteActivity, deleteDepartment, deleteProject,
  fetchAccounts, fetchActivities, fetchDepartments, fetchProjects,
  updateAccount, updateActivity, updateDepartment, updateProject,
} from "./api";

const KEYS = {
  departments: ["departments"],
  accounts: (filters) => ["accounts", filters ?? {}],
  projects: (filters) => ["projects", filters ?? {}],
  activities: (filters) => ["activities", filters ?? {}],
};

// ── Departments ───────────────────────────────────────────────────────────────

export function useDepartments() {
  return useQuery({ queryKey: KEYS.departments, queryFn: fetchDepartments, staleTime: 60_000 });
}

export function useCreateDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createDepartment,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.departments }),
  });
}

export function useUpdateDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ code, ...payload }) => updateDepartment(code, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.departments }),
  });
}

export function useDeleteDepartment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteDepartment,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.departments }),
  });
}

// ── Account Numbers ───────────────────────────────────────────────────────────

export function useAccounts(filters) {
  return useQuery({
    queryKey: KEYS.accounts(filters),
    queryFn: () => fetchAccounts(filters),
    staleTime: 60_000,
  });
}

export function useCreateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createAccount,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

export function useUpdateAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }) => updateAccount(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

export function useDeleteAccount() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["accounts"] }),
  });
}

// ── Project IDs ───────────────────────────────────────────────────────────────

export function useProjects(filters) {
  return useQuery({
    queryKey: KEYS.projects(filters),
    queryFn: () => fetchProjects(filters),
    staleTime: 30_000,
  });
}

export function useCreateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useUpdateProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }) => updateProject(id, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

export function useDeleteProject() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteProject,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["projects"] }),
  });
}

// ── Activity IDs ──────────────────────────────────────────────────────────────

export function useActivities(filters) {
  return useQuery({
    queryKey: KEYS.activities(filters),
    queryFn: () => fetchActivities(filters),
    staleTime: 30_000,
  });
}

export function useCreateActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createActivity,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities"] }),
  });
}

export function useUpdateActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ activityId, ...payload }) => updateActivity(activityId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities"] }),
  });
}

export function useDeleteActivity() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteActivity,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["activities"] }),
  });
}
