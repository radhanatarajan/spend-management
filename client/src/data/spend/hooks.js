import { useQuery } from "@tanstack/react-query";
import { fetchSpend, fetchSpendFilterOptions, fetchSpendSummary } from "./api";
import { QUERY_KEYS } from "./constants";

export function useSpend(filters) {
  return useQuery({
    queryKey: QUERY_KEYS.spend(filters),
    queryFn: () => fetchSpend(filters),
    staleTime: 30_000,
    placeholderData: (prev) => prev,
  });
}

export function useSpendFilterOptions(filters) {
  return useQuery({
    queryKey: QUERY_KEYS.spendFilterOptions(filters),
    queryFn: () => fetchSpendFilterOptions(filters),
    staleTime: 0,
    placeholderData: (prev) => prev,
  });
}

export function useSpendSummary(filters) {
  return useQuery({
    queryKey: QUERY_KEYS.spendSummary(filters),
    queryFn: () => fetchSpendSummary(filters),
    staleTime: 60_000,
    placeholderData: (prev) => prev,
  });
}
