"use client";

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api";

export interface FeatureFlag {
  key: string;
  label: string;
  description: string;
  enabled: boolean;
}

export function useFeatures() {
  return useQuery({
    queryKey: ["features"],
    queryFn: () => apiFetch<FeatureFlag[]>("/features"),
    staleTime: 30_000,
  });
}

// The server enforces every feature flag; this only decides what to show. Until the list
// loads, features count as on, so the page doesn't flash empty.
export function featureOn(features: FeatureFlag[] | undefined, key: string): boolean {
  return features?.find((f) => f.key === key)?.enabled ?? true;
}
