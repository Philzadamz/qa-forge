"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API_PREFIX, ApiError, apiFetch } from "@/lib/api";
import type { Run, RunStatus, RunStep, WorkspaceCase } from "@/lib/types/workspace";

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}

const STATUS_VARIANT: Record<RunStatus, "default" | "success" | "destructive" | "muted"> = {
  queued: "muted",
  running: "default",
  passed: "success",
  failed: "destructive",
  error: "destructive",
  cancelled: "muted",
};

const TERMINAL: RunStatus[] = ["passed", "failed", "error", "cancelled"];

interface LiveEvent {
  type: string;
  case_id?: string;
  display_id?: string;
  seq?: number;
  action?: string;
  outcome?: string;
  message?: string;
  status?: string;
  error?: string;
}

export function RunDetailClient({ runId }: { runId: string }) {
  const queryClient = useQueryClient();
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);

  const runKey = ["runs", runId];
  const { data: run } = useQuery({
    queryKey: runKey,
    queryFn: () => apiFetch<Run>(`/runs/${runId}`),
  });

  const { data: cases } = useQuery({
    queryKey: ["suites", run?.suite_id, "cases"],
    queryFn: () => apiFetch<WorkspaceCase[]>(`/suites/${run?.suite_id}/cases`),
    enabled: !!run?.suite_id,
  });

  const isTerminal = !!run && TERMINAL.includes(run.status);

  const { data: steps } = useQuery({
    queryKey: ["runs", runId, "steps"],
    queryFn: () => apiFetch<RunStep[]>(`/runs/${runId}/steps`),
    enabled: isTerminal,
  });

  useEffect(() => {
    if (!run || isTerminal) return;
    eventSourceRef.current?.close();
    const es = new EventSource(`${API_PREFIX}/runs/${runId}/events`, { withCredentials: true });
    eventSourceRef.current = es;
    es.onmessage = (event) => {
      const data = JSON.parse(event.data) as LiveEvent;
      if (data.type === "case_started") {
        setLog((prev) => [...prev, `▶ Starting ${data.display_id ?? data.case_id}`]);
      } else if (data.type === "step") {
        setLog((prev) => [
          ...prev,
          `  ${data.outcome === "pass" ? "✓" : data.outcome === "fail" ? "✗" : "⚠"} ${data.action}: ${data.message ?? ""}`,
        ]);
      } else if (data.type === "case_done") {
        setLog((prev) => [...prev, `  → ${data.status}`]);
      } else if (data.type === "run_done") {
        setLog((prev) => [
          ...prev,
          data.error ? `Run finished with an error: ${data.error}` : `Run finished: ${data.status}`,
        ]);
        queryClient.invalidateQueries({ queryKey: runKey });
        es.close();
      }
    };
    es.onerror = () => es.close();
    return () => es.close();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- runKey is derived from runId
  }, [run?.id, isTerminal]);

  const cancelRun = useMutation({
    mutationFn: () => apiFetch<Run>(`/runs/${runId}/cancel`, { method: "POST" }),
    onSuccess: (updated) => queryClient.setQueryData(runKey, updated),
    onError: (err: unknown) => setError(describeError(err, "Could not cancel the run.")),
  });

  const applyResults = useMutation({
    mutationFn: (caseIds: string[] | null) =>
      apiFetch<Run>(`/runs/${runId}/apply`, {
        method: "POST",
        body: JSON.stringify({ case_ids: caseIds }),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(runKey, updated);
      if (run?.suite_id) {
        queryClient.invalidateQueries({ queryKey: ["suites", run.suite_id, "cases"] });
      }
    },
    onError: (err: unknown) => setError(describeError(err, "Could not apply the results.")),
  });

  if (!run) return <p className="text-muted-foreground text-sm">Loading…</p>;

  const casesById = new Map((cases ?? []).map((c) => [c.id, c]));
  const caseResults = Object.entries(run.summary_json.cases ?? {});
  const anyUnapplied = caseResults.some(([, r]) => !r.applied);

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Test Lab Run</h1>
          <p className="text-muted-foreground text-sm">
            Started {run.started_at ? new Date(run.started_at).toLocaleString() : "—"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={STATUS_VARIANT[run.status]}>{run.status}</Badge>
          {(run.status === "queued" || run.status === "running") && (
            <Button
              variant="outline"
              onClick={() => cancelRun.mutate()}
              disabled={cancelRun.isPending}
            >
              Stop
            </Button>
          )}
        </div>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}
      {run.error && <p className="text-destructive text-sm">{run.error}</p>}

      {!isTerminal && (
        <Card>
          <CardHeader>
            <CardTitle>Live run</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="bg-muted max-h-96 overflow-y-auto rounded-md p-3 font-mono text-xs whitespace-pre-wrap">
              {log.length === 0 ? "Waiting for the run to start…" : log.join("\n")}
            </div>
          </CardContent>
        </Card>
      )}

      {isTerminal && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>Results ({caseResults.length})</CardTitle>
            {anyUnapplied && (
              <Button onClick={() => applyResults.mutate(null)} disabled={applyResults.isPending}>
                {applyResults.isPending ? "Applying…" : "Apply all to suite"}
              </Button>
            )}
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            {caseResults.map(([caseId, result]) => {
              const c = casesById.get(caseId);
              return (
                <div key={caseId} className="rounded-md border p-3">
                  <div className="flex items-center justify-between gap-4">
                    <div>
                      <div className="flex items-center gap-2 text-sm font-medium">
                        {c ? `${c.display_id || "—"} · ${c.feature}` : caseId}
                        <Badge variant={result.status === "Passed" ? "success" : "destructive"}>
                          {result.status}
                        </Badge>
                        <Badge variant="muted">{result.mode}</Badge>
                        {result.applied && <Badge variant="default">Applied</Badge>}
                      </div>
                      {c && <div className="text-muted-foreground text-sm">{c.scenario}</div>}
                      <div className="mt-1 text-sm">{result.actual_result}</div>
                    </div>
                    {!result.applied && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => applyResults.mutate([caseId])}
                        disabled={applyResults.isPending}
                      >
                        Apply
                      </Button>
                    )}
                  </div>
                </div>
              );
            })}
            {caseResults.length === 0 && (
              <p className="text-muted-foreground text-sm">No case results on this run.</p>
            )}
          </CardContent>
        </Card>
      )}

      {isTerminal && steps && steps.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Step log</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            {steps.map((s) => (
              <div
                key={s.id}
                className="flex items-start gap-3 border-b pb-2 text-sm last:border-0"
              >
                <span className="text-muted-foreground w-8 shrink-0">#{s.seq}</span>
                <span
                  className={
                    s.outcome === "pass"
                      ? "text-green-700"
                      : s.outcome === "fail" || s.outcome === "error"
                        ? "text-destructive"
                        : "text-muted-foreground"
                  }
                >
                  {s.outcome}
                </span>
                <span className="font-medium">{s.action}</span>
                {s.target && <span className="text-muted-foreground">{s.target}</span>}
                {s.input_masked && <span className="text-muted-foreground">{s.input_masked}</span>}
                <span className="flex-1">{s.message}</span>
                {s.screenshot_evidence_id && (
                  // eslint-disable-next-line @next/next/no-img-element -- internal, non-optimized step screenshot thumbnail
                  <img
                    src={`${API_PREFIX}/evidence/${s.screenshot_evidence_id}/file`}
                    alt="Step screenshot"
                    className="h-12 w-12 rounded border object-cover"
                  />
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
