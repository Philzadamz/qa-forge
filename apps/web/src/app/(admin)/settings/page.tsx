"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Card, CardContent } from "@/components/ui/card";
import { ApiError, apiFetch } from "@/lib/api";
import type { FeatureFlag } from "@/lib/features";

export default function SettingsPage() {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);

  const { data: features, isLoading } = useQuery({
    queryKey: ["admin", "features"],
    queryFn: () => apiFetch<FeatureFlag[]>("/admin/features"),
  });

  const toggle = useMutation({
    mutationFn: ({ key, enabled }: { key: string; enabled: boolean }) =>
      apiFetch<FeatureFlag[]>(`/admin/features/${key}`, {
        method: "PUT",
        body: JSON.stringify({ enabled }),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["admin", "features"], updated);
      queryClient.invalidateQueries({ queryKey: ["features"] });
      setError(null);
    },
    onError: (err: unknown) =>
      setError(err instanceof ApiError ? (err.problem.detail ?? err.message) : "Could not save."),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="text-muted-foreground text-sm">
          Turn features on or off for everyone. A feature that is off is hidden in the app and
          refused by the server, so it can&apos;t be used even through a direct request.
        </p>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}
      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}

      <Card>
        <CardContent className="flex flex-col divide-y p-0">
          {features?.map((f) => (
            <div key={f.key} className="flex items-center justify-between gap-6 px-6 py-4">
              <div className="flex flex-col">
                <span className="font-medium">{f.label}</span>
                <span className="text-muted-foreground text-sm">{f.description}</span>
                <span className="text-muted-foreground font-mono text-xs">{f.key}</span>
              </div>
              <button
                type="button"
                role="switch"
                aria-checked={f.enabled}
                aria-label={`${f.label} ${f.enabled ? "on" : "off"}`}
                disabled={toggle.isPending}
                onClick={() => toggle.mutate({ key: f.key, enabled: !f.enabled })}
                className={`focus-visible:ring-ring relative inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-60 ${
                  f.enabled ? "bg-primary" : "bg-muted-foreground/40"
                }`}
              >
                <span
                  className={`inline-block h-5 w-5 transform rounded-full bg-white shadow transition-transform ${
                    f.enabled ? "translate-x-5" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
