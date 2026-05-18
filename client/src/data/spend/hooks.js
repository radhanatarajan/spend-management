import { useQuery } from "@tanstack/react-query";
import { fetchSpend, fetchSpendFilterOptions } from "./api";
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
