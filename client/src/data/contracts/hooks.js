import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchContracts, fetchContract,
  createContract, updateContract, deleteContract,
  addContractLine, updateContractLine, deleteContractLine,
  fetchContractReport,
} from "./api";

const KEYS = {
  all: ["contracts"],
  detail: (id) => ["contracts", id],
};

export function useContracts() {
  return useQuery({
    queryKey: KEYS.all,
    queryFn: fetchContracts,
    staleTime: 30_000,
  });
}

export function useContract(id) {
  return useQuery({
    queryKey: KEYS.detail(id),
    queryFn: () => fetchContract(id),
    enabled: id != null,
  });
}

export function useCreateContract() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createContract,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  });
}

export function useUpdateContract() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...payload }) => updateContract(id, payload),
    onSuccess: (_, { id }) => {
      qc.invalidateQueries({ queryKey: KEYS.all });
      qc.invalidateQueries({ queryKey: KEYS.detail(id) });
    },
  });
}

export function useDeleteContract() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: deleteContract,
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  });
}

export function useAddContractLine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contractId, ...payload }) => addContractLine(contractId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  });
}

export function useUpdateContractLine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contractId, lineId, ...payload }) => updateContractLine(contractId, lineId, payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  });
}

export function useDeleteContractLine() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ contractId, lineId }) => deleteContractLine(contractId, lineId),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all }),
  });
}

export function useContractReport(fiscalYear) {
  return useQuery({
    queryKey: ["contractReport", fiscalYear],
    queryFn: () => fetchContractReport(fiscalYear),
    enabled: fiscalYear != null,
    staleTime: 30_000,
  });
}
