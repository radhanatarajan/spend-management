import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchCostElements, fetchAccountGroups, fetchAccountSubGroups,
  fetchNcConfig, updateNcConfig,
  fetchScenarios, createScenario, updateScenario, deleteScenario,
  fetchNonControllablePlan, upsertEntry, deleteEntry,
  fetchScenarioComparison, updateEntryStatus, fetchScenarioAudit,
  fetchBudgetAuditReport,
  fetchControllablePlan, fetchControllableComparison,
  upsertControllableEntry, deleteControllableEntry,
  updateControllableEntryStatus, upsertLineOverride,
  fetchBudgetReport,
} from "./api";

const KEYS = {
  costElements: ["budget", "costElements"],
  accountGroups: ["budget", "accountGroups"],
  accountSubGroups: ["budget", "accountSubGroups"],
  ncConfig: (fy) => ["budget", "ncConfig", fy],
  scenarios: (fy, type) => ["budget", "scenarios", fy, type],
  ncPlan: (fy, scenarioId) => ["budget", "ncPlan", fy, scenarioId],
  controllablePlan: (fy, scenarioId) => ["budget", "controllablePlan", fy, scenarioId],
  budgetReport: (fy, ncId, ctrlId) => ["budget", "report", fy, ncId, ctrlId],
};

export function useCostElements() {
  return useQuery({
    queryKey: KEYS.costElements,
    queryFn: fetchCostElements,
    staleTime: 300_000,
  });
}

export function useAccountGroups() {
  return useQuery({
    queryKey: KEYS.accountGroups,
    queryFn: fetchAccountGroups,
    staleTime: 300_000,
  });
}

export function useAccountSubGroups() {
  return useQuery({
    queryKey: KEYS.accountSubGroups,
    queryFn: fetchAccountSubGroups,
    staleTime: 300_000,
  });
}

export function useNcConfig(fiscalYear) {
  return useQuery({
    queryKey: KEYS.ncConfig(fiscalYear),
    queryFn: () => fetchNcConfig(fiscalYear),
    enabled: fiscalYear != null,
    staleTime: 60_000,
  });
}

export function useUpdateNcConfig() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: updateNcConfig,
    onSuccess: (data) => {
      qc.setQueryData(KEYS.ncConfig(data.fiscal_year), data);
      qc.invalidateQueries({ queryKey: ["budget", "ncPlan"] });
    },
  });
}

export function useScenarios(fiscalYear, budgetType) {
  return useQuery({
    queryKey: KEYS.scenarios(fiscalYear, budgetType),
    queryFn: () => fetchScenarios(fiscalYear, budgetType),
    enabled: fiscalYear != null && budgetType != null,
    staleTime: 30_000,
  });
}

export function useCreateScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createScenario,
    onSuccess: (data) => {
      qc.invalidateQueries({ queryKey: KEYS.scenarios(data.fiscal_year, data.budget_type) });
    },
  });
}

export function useUpdateScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }) => updateScenario(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget", "scenarios"] });
      qc.invalidateQueries({ queryKey: ["budget", "ncPlan"] });
    },
  });
}

export function useDeleteScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteScenario,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget", "scenarios"] });
    },
  });
}

export function useNonControllablePlan(fiscalYear, scenarioId) {
  return useQuery({
    queryKey: KEYS.ncPlan(fiscalYear, scenarioId),
    queryFn: () => fetchNonControllablePlan(fiscalYear, scenarioId),
    enabled: fiscalYear != null && scenarioId != null,
    staleTime: 30_000,
  });
}

export function useUpsertEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: upsertEntry,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget", "ncPlan"] });
      qc.invalidateQueries({ queryKey: ["budget", "audit"] });
    },
  });
}

export function useDeleteEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteEntry,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget", "ncPlan"] });
    },
  });
}

export function useUpdateEntryStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }) => updateEntryStatus(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget", "ncPlan"] });
      qc.invalidateQueries({ queryKey: ["budget", "audit"] });
    },
  });
}

export function useScenarioAudit(scenarioId) {
  return useQuery({
    queryKey: ["budget", "audit", scenarioId],
    queryFn: () => fetchScenarioAudit(scenarioId),
    enabled: scenarioId != null,
    staleTime: 10_000,
  });
}

export function useBudgetAuditReport(fiscalYear) {
  return useQuery({
    queryKey: ["budget", "auditReport", fiscalYear],
    queryFn: () => fetchBudgetAuditReport(fiscalYear),
    enabled: fiscalYear != null,
    staleTime: 30_000,
  });
}

export function useScenarioComparison(fiscalYear, scenarioAId, scenarioBId) {
  return useQuery({
    queryKey: ["budget", "compare", fiscalYear, scenarioAId, scenarioBId],
    queryFn: () => fetchScenarioComparison(fiscalYear, scenarioAId, scenarioBId),
    enabled: fiscalYear != null && scenarioAId != null && scenarioBId != null && scenarioAId !== scenarioBId,
    staleTime: 30_000,
  });
}

export function useControllablePlan(fiscalYear, scenarioId) {
  return useQuery({
    queryKey: KEYS.controllablePlan(fiscalYear, scenarioId),
    queryFn: () => fetchControllablePlan(fiscalYear, scenarioId),
    enabled: fiscalYear != null && scenarioId != null,
    staleTime: 30_000,
  });
}

export function useUpsertControllableEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: upsertControllableEntry,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget", "controllablePlan"] });
    },
  });
}

export function useDeleteControllableEntry() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteControllableEntry,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget", "controllablePlan"] });
    },
  });
}

export function useUpdateControllableEntryStatus() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }) => updateControllableEntryStatus(id, status),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["budget", "controllablePlan"] });
    },
  });
}

export function useControllableComparison(fiscalYear, scenarioAId, scenarioBId) {
  return useQuery({
    queryKey: ["budget", "ctrlCompare", fiscalYear, scenarioAId, scenarioBId],
    queryFn: () => fetchControllableComparison(fiscalYear, scenarioAId, scenarioBId),
    enabled: fiscalYear != null && scenarioAId != null && scenarioBId != null && scenarioAId !== scenarioBId,
    staleTime: 30_000,
  });
}

export function useBudgetReport(fiscalYear, scenarioNcId, scenarioCtrlId) {
  return useQuery({
    queryKey: KEYS.budgetReport(fiscalYear, scenarioNcId, scenarioCtrlId),
    queryFn: () => fetchBudgetReport(fiscalYear, scenarioNcId, scenarioCtrlId),
    enabled: fiscalYear != null,
    staleTime: 30_000,
  });
}

export function useUpsertLineOverride() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: upsertLineOverride,
    onSuccess: () => {
      qc.refetchQueries({ queryKey: ["budget", "controllablePlan"] });
    },
  });
}
