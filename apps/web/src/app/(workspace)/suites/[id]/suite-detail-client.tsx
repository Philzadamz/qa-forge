"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { memo, useCallback, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { BackButton } from "@/components/back-button";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ApiError, apiFetch, apiFetchBlob } from "@/lib/api";
import { featureOn, useFeatures } from "@/lib/features";
import type { Report, Suite, TestStatusValue, WorkspaceCase } from "@/lib/types/workspace";

import { BugsPanel } from "./bugs-panel";
import { GenerationCard } from "./generation-card";
import { TestLabPanel } from "./test-lab-panel";

const STATUS_VALUES: TestStatusValue[] = [
  "Not Tested",
  "Passed",
  "Failed",
  "Suspended",
  "Modification",
  "Blocked",
];

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}

const CaseCard = memo(function CaseCard({
  c,
  onToggleInclude,
  onDelete,
  onPatch,
  onDraftBug,
  selectedForRun,
  onToggleForRun,
}: {
  c: WorkspaceCase;
  onToggleInclude: (id: string, included: boolean) => void;
  onDelete: (id: string) => void;
  onPatch: (
    id: string,
    patch: Partial<Pick<WorkspaceCase, "status" | "actual_result" | "is_regression">>,
  ) => void;
  onDraftBug?: (id: string) => void;
  selectedForRun: boolean;
  onToggleForRun: (id: string, checked: boolean) => void;
}) {
  const statusVariant =
    c.status === "Passed" ? "success" : c.status === "Failed" ? "destructive" : "muted";
  return (
    <Card className={c.included ? undefined : "opacity-50"}>
      <CardContent className="flex flex-col gap-3 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1">
            <div className="text-muted-foreground flex items-center gap-2 text-xs font-medium tracking-wide uppercase">
              <span>
                {c.display_id || "—"} · {c.feature}
              </span>
              <Badge variant={statusVariant}>{c.status}</Badge>
              {c.is_duplicate && <Badge variant="destructive">Possible duplicate</Badge>}
              {c.source === "ai" && <Badge>AI</Badge>}
            </div>
            <div className="font-medium">{c.scenario}</div>
            <ol className="text-muted-foreground mt-1 list-inside list-decimal text-sm">
              {c.steps.map((step, i) => (
                <li key={i}>{step}</li>
              ))}
            </ol>
            <div className="mt-1 text-sm">
              <span className="text-muted-foreground">Expected: </span>
              {c.expected_result}
            </div>
          </div>
          <div className="flex shrink-0 flex-col items-end gap-2">
            <label className="hover:bg-muted flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-sm select-none">
              Include
              <Checkbox
                checked={c.included}
                onChange={(e) => onToggleInclude(c.id, e.target.checked)}
              />
            </label>
            <label className="hover:bg-muted flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-sm select-none">
              Run in Test Lab
              <Checkbox
                checked={selectedForRun}
                onChange={(e) => onToggleForRun(c.id, e.target.checked)}
              />
            </label>
            <Button variant="destructive" size="sm" onClick={() => onDelete(c.id)}>
              Delete
            </Button>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 border-t pt-3 md:grid-cols-[160px_1fr_auto]">
          <div className="flex flex-col gap-1">
            <Label htmlFor={`status-${c.id}`} className="text-xs">
              Status
            </Label>
            <Select
              id={`status-${c.id}`}
              value={c.status}
              onChange={(e) => onPatch(c.id, { status: e.target.value as TestStatusValue })}
              className="h-9"
            >
              {STATUS_VALUES.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </Select>
            <label className="flex items-center gap-2 text-xs">
              <Checkbox
                checked={c.is_regression}
                onChange={(e) => onPatch(c.id, { is_regression: e.target.checked })}
              />
              Regression
            </label>
          </div>
          <div className="flex flex-col gap-1">
            <Label htmlFor={`actual-${c.id}`} className="text-xs">
              Actual result
            </Label>
            <Input
              id={`actual-${c.id}`}
              defaultValue={c.actual_result}
              onBlur={(e) => {
                if (e.target.value !== c.actual_result)
                  onPatch(c.id, { actual_result: e.target.value });
              }}
            />
          </div>
          {c.status === "Failed" && onDraftBug && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDraftBug?.(c.id)}
              className="self-start"
            >
              File bug
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
});

export function SuiteDetailClient({ suiteId }: { suiteId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [selectedForRun, setSelectedForRun] = useState<Set<string>>(new Set());

  const toggleForRun = useCallback((id: string, checked: boolean) => {
    setSelectedForRun((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }, []);

  const { data: features } = useFeatures();
  const reportsOn = featureOn(features, "report_generation");
  const aiOn = featureOn(features, "ai_case_generation");
  const bugsOn = featureOn(features, "bug_tracking");

  const casesKey = ["suites", suiteId, "cases"];

  const { data: suite } = useQuery({
    queryKey: ["suites", suiteId],
    queryFn: () => apiFetch<Suite>(`/suites/${suiteId}`),
  });
  const { data: cases } = useQuery({
    queryKey: casesKey,
    queryFn: () => apiFetch<WorkspaceCase[]>(`/suites/${suiteId}/cases`),
  });
  const toggleInclude = useMutation({
    mutationFn: ({ id, included }: { id: string; included: boolean }) =>
      apiFetch<WorkspaceCase>(`/cases/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ included }),
      }),
    onMutate: async (vars: { id: string; included: boolean }) => {
      await queryClient.cancelQueries({ queryKey: casesKey });
      const previous = queryClient.getQueryData<WorkspaceCase[]>(casesKey);
      queryClient.setQueryData<WorkspaceCase[]>(casesKey, (old) =>
        old?.map((c) => (c.id === vars.id ? { ...c, included: vars.included } : c)),
      );
      return { previous };
    },
    onError: (err: unknown, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(casesKey, ctx.previous);
      setError(describeError(err, "Could not save that change."));
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: casesKey }),
  });

  const deleteCase = useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/cases/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: casesKey }),
    onError: (err: unknown) => setError(describeError(err, "Could not delete the case.")),
  });

  const patchCase = useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: string;
      patch: Partial<Pick<WorkspaceCase, "status" | "actual_result" | "is_regression">>;
    }) => apiFetch<WorkspaceCase>(`/cases/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    onMutate: async ({ id, patch }) => {
      await queryClient.cancelQueries({ queryKey: casesKey });
      const previous = queryClient.getQueryData<WorkspaceCase[]>(casesKey);
      queryClient.setQueryData<WorkspaceCase[]>(casesKey, (old) =>
        old?.map((c) => (c.id === id ? { ...c, ...patch } : c)),
      );
      return { previous };
    },
    onError: (err: unknown, _vars, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(casesKey, ctx.previous);
      setError(describeError(err, "Could not save that change."));
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: casesKey }),
  });

  const draftBug = useMutation({
    mutationFn: (caseId: string) => apiFetch(`/cases/${caseId}/bugs/draft`, { method: "POST" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["suites", suiteId, "bugs"] }),
    onError: (err: unknown) => setError(describeError(err, "Could not file a bug.")),
  });

  const markAllPassed = useMutation({
    mutationFn: () => {
      const includedIds = (cases ?? []).filter((c) => c.included).map((c) => c.id);
      return apiFetch<WorkspaceCase[]>(`/suites/${suiteId}/cases/bulk`, {
        method: "POST",
        body: JSON.stringify({
          case_ids: includedIds,
          status: "Passed",
          actual_result: "As expected",
        }),
      });
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: casesKey }),
    onError: (err: unknown) => setError(describeError(err, "Could not update the cases.")),
  });

  const draftReport = useMutation({
    mutationFn: () => apiFetch<Report>(`/suites/${suiteId}/reports/draft`, { method: "POST" }),
    onSuccess: (report) => router.push(`/reports/${report.id}`),
    onError: (err: unknown) => setError(describeError(err, "Could not draft the report.")),
  });

  const { mutate: toggleIncludeMutate } = toggleInclude;
  const { mutate: deleteCaseMutate } = deleteCase;
  const { mutate: patchCaseMutate } = patchCase;
  const { mutate: draftBugMutate } = draftBug;
  const handleToggleInclude = useCallback(
    (id: string, included: boolean) => toggleIncludeMutate({ id, included }),
    [toggleIncludeMutate],
  );
  const handleDelete = useCallback((id: string) => deleteCaseMutate(id), [deleteCaseMutate]);
  const handlePatch = useCallback(
    (id: string, patch: Parameters<typeof patchCaseMutate>[0]["patch"]) =>
      patchCaseMutate({ id, patch }),
    [patchCaseMutate],
  );
  const handleDraftBug = useCallback((id: string) => draftBugMutate(id), [draftBugMutate]);

  const [exporting, setExporting] = useState(false);

  async function handleExport() {
    setError(null);
    setExporting(true);
    try {
      const blob = await apiFetchBlob(`/suites/${suiteId}/export/xlsx`, { method: "POST" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${suite?.name ?? "suite"}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(describeError(err, "Could not export the xlsx file."));
    } finally {
      setExporting(false);
    }
  }

  if (!suite) return <p className="text-muted-foreground text-sm">Loading…</p>;

  const defaults = cases?.filter((c) => c.section === "default") ?? [];
  const functional = cases?.filter((c) => c.section === "functional") ?? [];

  return (
    <div className="flex flex-col gap-6">
      <BackButton fallbackHref={`/projects/${suite.project_id}`} label="Back to project" />
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{suite.name}</h1>
          <p className="text-muted-foreground text-sm">
            {String(suite.header_json.project_name_line ?? "")}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="outline"
            onClick={() => markAllPassed.mutate()}
            loading={markAllPassed.isPending}
            disabled={!cases?.length}
          >
            Mark all as Passed
          </Button>
          {reportsOn && (
            <Button
              variant="outline"
              onClick={() => draftReport.mutate()}
              loading={draftReport.isPending}
            >
              {draftReport.isPending ? "Generating report…" : "Generate Report"}
            </Button>
          )}
          <Button onClick={handleExport} loading={exporting}>
            {exporting ? "Preparing file…" : "Download Test Cases (.xlsx)"}
          </Button>
        </div>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <div>
        <h2 className="mb-2 text-lg font-semibold">Default scenarios ({defaults.length})</h2>
        <div className="flex flex-col gap-3">
          {defaults.map((c) => (
            <CaseCard
              key={c.id}
              c={c}
              onToggleInclude={handleToggleInclude}
              onDelete={handleDelete}
              onPatch={handlePatch}
              onDraftBug={bugsOn ? handleDraftBug : undefined}
              selectedForRun={selectedForRun.has(c.id)}
              onToggleForRun={toggleForRun}
            />
          ))}
        </div>
      </div>

      {aiOn && <GenerationCard suiteId={suiteId} projectId={suite.project_id} />}

      {functional.length > 0 && (
        <div>
          <h2 className="mb-2 text-lg font-semibold">Functional scenarios ({functional.length})</h2>
          <div className="flex flex-col gap-3">
            {functional.map((c) => (
              <CaseCard
                key={c.id}
                c={c}
                onToggleInclude={handleToggleInclude}
                onDelete={handleDelete}
                onPatch={handlePatch}
                onDraftBug={bugsOn ? handleDraftBug : undefined}
                selectedForRun={selectedForRun.has(c.id)}
                onToggleForRun={toggleForRun}
              />
            ))}
          </div>
        </div>
      )}

      <TestLabPanel
        suiteId={suiteId}
        projectId={suite.project_id}
        selectedCaseIds={[...selectedForRun]}
        onRunStarted={() => setSelectedForRun(new Set())}
      />

      {bugsOn && <BugsPanel suiteId={suiteId} />}
    </div>
  );
}
