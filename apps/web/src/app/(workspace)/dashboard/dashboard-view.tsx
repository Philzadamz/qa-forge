"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";
import type { Dashboard, RecentRun } from "@/lib/types/dashboard";

const STATUS_VARIANT: Record<RecentRun["status"], "default" | "success" | "destructive" | "muted"> =
  {
    queued: "muted",
    running: "default",
    passed: "success",
    failed: "destructive",
    error: "destructive",
    cancelled: "muted",
  };

function Stat({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-1 py-5">
        <span className="text-muted-foreground text-sm">{label}</span>
        <span className="text-2xl font-semibold tracking-tight">{value}</span>
        {hint && <span className="text-muted-foreground text-xs">{hint}</span>}
      </CardContent>
    </Card>
  );
}

export function DashboardView() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiFetch<Dashboard>("/dashboard"),
  });

  if (isLoading) return <p className="text-muted-foreground text-sm">Loading…</p>;
  if (isError || !data) {
    return <p className="text-destructive text-sm">Could not load the dashboard.</p>;
  }

  const passRate =
    data.pass_rate_30_days === null ? "—" : `${Math.round(data.pass_rate_30_days * 100)}%`;
  const totalTokens = data.usage.prompt_tokens + data.usage.completion_tokens;

  return (
    <div className="flex flex-col gap-6">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        <Stat label="Projects" value={data.project_count.toLocaleString()} />
        <Stat label="Suites" value={data.suite_count.toLocaleString()} />
        <Stat
          label="Runs (30 days)"
          value={data.run_count_30_days.toLocaleString()}
          hint={`Pass rate ${passRate}`}
        />
        <Stat
          label="AI tokens (30 days)"
          value={totalTokens.toLocaleString()}
          hint={`${data.usage.prompt_tokens.toLocaleString()} in · ${data.usage.completion_tokens.toLocaleString()} out`}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Recent runs</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {data.recent_runs.length === 0 && (
              <p className="text-muted-foreground text-sm">No Test Lab runs yet.</p>
            )}
            {data.recent_runs.map((run) => (
              <Link
                key={run.id}
                href={`/runs/${run.id}`}
                className="hover:bg-muted flex items-center justify-between rounded-md border px-3 py-2 text-sm"
              >
                <span className="flex flex-col">
                  <span className="font-medium">{run.suite_name ?? "Suite"}</span>
                  <span className="text-muted-foreground text-xs">
                    {run.target} · {new Date(run.created_at).toLocaleString()}
                  </span>
                </span>
                <span className="flex items-center gap-2">
                  {run.total > 0 && (
                    <span className="text-muted-foreground">
                      {run.passed}/{run.total} passed
                    </span>
                  )}
                  <Badge variant={STATUS_VARIANT[run.status]}>{run.status}</Badge>
                </span>
              </Link>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>AI usage (last {data.usage.window_days} days)</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            {data.usage.by_feature.length === 0 ? (
              <p className="text-muted-foreground text-sm">No AI calls in this window.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="text-muted-foreground text-left">
                  <tr>
                    <th className="pb-2 font-medium">Feature</th>
                    <th className="pb-2 text-right font-medium">Input</th>
                    <th className="pb-2 text-right font-medium">Output</th>
                  </tr>
                </thead>
                <tbody>
                  {data.usage.by_feature.map((row) => (
                    <tr key={row.feature} className="border-t">
                      <td className="py-2">{row.feature.replaceAll("_", " ")}</td>
                      <td className="py-2 text-right">{row.prompt_tokens.toLocaleString()}</td>
                      <td className="py-2 text-right">{row.completion_tokens.toLocaleString()}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
            <p className="text-muted-foreground text-xs">
              Estimated cost: ${data.usage.cost_estimate.toFixed(4)}. This stays at $0 until the
              operator sets AI_COST_PER_MILLION_INPUT_TOKENS / _OUTPUT_TOKENS.
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
