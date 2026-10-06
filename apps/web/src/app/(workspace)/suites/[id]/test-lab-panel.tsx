"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ApiError, apiFetch } from "@/lib/api";
import type { Apk, Project, Run, RunStatus } from "@/lib/types/workspace";

import { ApiSpecPanel } from "./api-spec-panel";

type Target = "web" | "api" | "android";

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

export function TestLabPanel({
  suiteId,
  projectId,
  selectedCaseIds,
  onRunStarted,
}: {
  suiteId: string;
  projectId: string;
  selectedCaseIds: string[];
  onRunStarted: () => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [target, setTarget] = useState<Target>("web");
  const [targetUrl, setTargetUrl] = useState("");
  const [apkId, setApkId] = useState("");
  const [error, setError] = useState<string | null>(null);

  const { data: project } = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => apiFetch<Project>(`/projects/${projectId}`),
  });
  const { data: runs } = useQuery({
    queryKey: ["suites", suiteId, "runs"],
    queryFn: () => apiFetch<Run[]>(`/suites/${suiteId}/runs`),
  });
  const { data: apks } = useQuery({
    queryKey: ["projects", projectId, "apks"],
    queryFn: () => apiFetch<Apk[]>(`/projects/${projectId}/apks`),
    enabled: target === "android",
  });

  const effectiveUrl = targetUrl || project?.default_test_url || "";
  const canStart = selectedCaseIds.length > 0 && (target === "android" ? !!apkId : !!effectiveUrl);

  const startRun = useMutation({
    mutationFn: () =>
      apiFetch<Run>("/runs", {
        method: "POST",
        body: JSON.stringify({
          suite_id: suiteId,
          case_ids: selectedCaseIds,
          target,
          target_url: target === "android" ? undefined : effectiveUrl || undefined,
          apk_id: target === "android" ? apkId : undefined,
        }),
      }),
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["suites", suiteId, "runs"] });
      onRunStarted();
      router.push(`/runs/${run.id}`);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not start the run.")),
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Test Lab</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="target">Target</Label>
          <Select
            id="target"
            value={target}
            onChange={(e) => setTarget(e.target.value as Target)}
            className="w-40"
          >
            <option value="web">Web</option>
            <option value="api">API</option>
            <option value="android">Android</option>
          </Select>
        </div>

        {target === "api" && <ApiSpecPanel suiteId={suiteId} />}

        {target === "android" ? (
          <div className="flex flex-col gap-2">
            <Label htmlFor="apk-select">APK</Label>
            <Select id="apk-select" value={apkId} onChange={(e) => setApkId(e.target.value)}>
              <option value="">Select an uploaded APK…</option>
              {apks?.map((apk) => (
                <option key={apk.id} value={apk.id}>
                  {apk.label || apk.file_name} (v{apk.version_name})
                </option>
              ))}
            </Select>
            {apks?.length === 0 && (
              <p className="text-muted-foreground text-xs">
                No APKs uploaded yet — upload one on the project page first.
              </p>
            )}
            <p className="text-muted-foreground text-xs">
              {selectedCaseIds.length === 0
                ? "Check “Run in Test Lab” on one or more cases above, then start a run."
                : `${selectedCaseIds.length} case(s) selected to run.`}
            </p>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <Label htmlFor="target-url">{target === "api" ? "Base URL" : "Target URL"}</Label>
            <Input
              id="target-url"
              placeholder={project?.default_test_url ?? "https://…"}
              value={targetUrl}
              onChange={(e) => setTargetUrl(e.target.value)}
            />
            <p className="text-muted-foreground text-xs">
              {selectedCaseIds.length === 0
                ? "Check “Run in Test Lab” on one or more cases above, then start a run."
                : `${selectedCaseIds.length} case(s) selected to run.`}
            </p>
          </div>
        )}
        {error && <p className="text-destructive text-sm">{error}</p>}
        <Button
          onClick={() => startRun.mutate()}
          disabled={!canStart || startRun.isPending}
          loading={startRun.isPending}
          className="self-start"
        >
          {startRun.isPending ? "Starting…" : "Start Test Lab Run"}
        </Button>

        {runs && runs.length > 0 && (
          <div className="flex flex-col gap-2 border-t pt-4">
            <h3 className="text-sm font-medium">Past runs</h3>
            {runs.map((r) => (
              <a
                key={r.id}
                href={`/runs/${r.id}`}
                className="hover:bg-muted flex items-center justify-between rounded-md border px-3 py-2 text-sm"
              >
                <span>{new Date(r.created_at).toLocaleString()}</span>
                <span className="flex items-center gap-2">
                  {typeof r.summary_json.total === "number" && (
                    <span className="text-muted-foreground">
                      {r.summary_json.passed ?? 0}/{r.summary_json.total} passed
                    </span>
                  )}
                  <Badge variant={STATUS_VARIANT[r.status]}>{r.status}</Badge>
                </span>
              </a>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
