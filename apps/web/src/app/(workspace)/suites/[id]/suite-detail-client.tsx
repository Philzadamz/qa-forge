"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { API_PREFIX, ApiError, apiFetch } from "@/lib/api";
import { pasteStorySchema, type PasteStoryInput } from "@/lib/schemas/workspace";
import type {
  GenerationJob,
  Report,
  Story,
  Suite,
  TestStatusValue,
  WorkspaceCase,
} from "@/lib/types/workspace";

import { BugsPanel } from "./bugs-panel";
import { CaseEvidence } from "./case-evidence";
import { TestLabPanel } from "./test-lab-panel";

const COVERAGE_DEPTHS = ["Essential", "Standard", "Exhaustive"] as const;
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

function CaseCard({
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
  onDraftBug: (id: string) => void;
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
            <label className="flex items-center gap-2 text-sm">
              Include
              <Checkbox
                checked={c.included}
                onChange={(e) => onToggleInclude(c.id, e.target.checked)}
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
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
            <CaseEvidence caseId={c.id} />
          </div>
          {c.status === "Failed" && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => onDraftBug(c.id)}
              className="self-start"
            >
              File bug
            </Button>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

export function SuiteDetailClient({ suiteId }: { suiteId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const [selectedStoryIds, setSelectedStoryIds] = useState<string[]>([]);
  const [coverageDepth, setCoverageDepth] = useState<(typeof COVERAGE_DEPTHS)[number]>("Standard");
  const [additionalContext, setAdditionalContext] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [progressLines, setProgressLines] = useState<string[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const [selectedForRun, setSelectedForRun] = useState<Set<string>>(new Set());

  function toggleForRun(id: string, checked: boolean) {
    setSelectedForRun((prev) => {
      const next = new Set(prev);
      if (checked) next.add(id);
      else next.delete(id);
      return next;
    });
  }

  const casesKey = ["suites", suiteId, "cases"];

  const { data: suite } = useQuery({
    queryKey: ["suites", suiteId],
    queryFn: () => apiFetch<Suite>(`/suites/${suiteId}`),
  });
  const { data: cases } = useQuery({
    queryKey: casesKey,
    queryFn: () => apiFetch<WorkspaceCase[]>(`/suites/${suiteId}/cases`),
  });
  const { data: stories } = useQuery({
    queryKey: ["projects", suite?.project_id, "stories"],
    queryFn: () => apiFetch<Story[]>(`/projects/${suite?.project_id}/stories`),
    enabled: !!suite?.project_id,
  });
  const { data: job } = useQuery({
    queryKey: ["jobs", activeJobId],
    queryFn: () => apiFetch<GenerationJob>(`/jobs/${activeJobId}`),
    enabled: !!activeJobId,
    refetchInterval: (query) =>
      query.state.data?.status === "succeeded" || query.state.data?.status === "failed"
        ? false
        : 2000,
  });

  const {
    register: registerPaste,
    handleSubmit: handlePasteSubmit,
    reset: resetPaste,
    formState: { errors: pasteErrors, isSubmitting: isPasting },
  } = useForm<PasteStoryInput>({ resolver: zodResolver(pasteStorySchema) });

  const pasteStory = useMutation({
    mutationFn: (values: PasteStoryInput) =>
      apiFetch<Story>(`/projects/${suite?.project_id}/stories/paste`, {
        method: "POST",
        body: JSON.stringify(values),
      }),
    onSuccess: (story) => {
      queryClient.invalidateQueries({ queryKey: ["projects", suite?.project_id, "stories"] });
      setSelectedStoryIds((prev) => [...prev, story.id]);
      resetPaste();
      setShowPaste(false);
    },
  });

  const toggleInclude = useMutation({
    mutationFn: ({ id, included }: { id: string; included: boolean }) =>
      apiFetch<WorkspaceCase>(`/cases/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ included }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: casesKey }),
  });

  const deleteCase = useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/cases/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: casesKey }),
  });

  const patchCase = useMutation({
    mutationFn: ({
      id,
      patch,
    }: {
      id: string;
      patch: Partial<Pick<WorkspaceCase, "status" | "actual_result" | "is_regression">>;
    }) => apiFetch<WorkspaceCase>(`/cases/${id}`, { method: "PATCH", body: JSON.stringify(patch) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: casesKey }),
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

  const startGeneration = useMutation({
    mutationFn: () =>
      apiFetch<GenerationJob>(`/suites/${suiteId}/generate`, {
        method: "POST",
        body: JSON.stringify({
          story_ids: selectedStoryIds,
          coverage_depth: coverageDepth,
          additional_context: additionalContext,
        }),
      }),
    onSuccess: (newJob) => {
      setActiveJobId(newJob.id);
      setProgressLines([]);
      setError(null);

      eventSourceRef.current?.close();
      const es = new EventSource(`${API_PREFIX}/jobs/${newJob.id}/events`, {
        withCredentials: true,
      });
      eventSourceRef.current = es;
      es.onmessage = (event) => {
        const data = JSON.parse(event.data) as {
          type: string;
          feature?: string;
          case_count?: number;
          status?: string;
          error?: string;
        };
        if (data.type === "feature_done") {
          setProgressLines((prev) => [...prev, `✓ ${data.feature} — ${data.case_count} case(s)`]);
          queryClient.invalidateQueries({ queryKey: casesKey });
        } else if (data.type === "job_done") {
          setProgressLines((prev) => [
            ...prev,
            data.status === "succeeded" ? "Done." : `Failed: ${data.error ?? "unknown error"}`,
          ]);
          queryClient.invalidateQueries({ queryKey: casesKey });
          queryClient.invalidateQueries({ queryKey: ["jobs", newJob.id] });
          es.close();
        }
      };
      es.onerror = () => es.close();
    },
    onError: (err: unknown) => setError(describeError(err, "Could not start generation.")),
  });

  async function handleExport() {
    setError(null);
    try {
      const res = await fetch(`${API_PREFIX}/suites/${suiteId}/export/xlsx`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${suite?.name ?? "suite"}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setError("Could not export the xlsx file.");
    }
  }

  if (!suite) return <p className="text-muted-foreground text-sm">Loading…</p>;

  const defaults = cases?.filter((c) => c.section === "default") ?? [];
  const functional = cases?.filter((c) => c.section === "functional") ?? [];
  const isGenerating = job?.status === "queued" || job?.status === "running";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{suite.name}</h1>
          <p className="text-muted-foreground text-sm">
            {String(suite.header_json.project_name_line ?? "")}
          </p>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() => markAllPassed.mutate()}
            disabled={markAllPassed.isPending || !cases?.length}
          >
            Mark all as Passed
          </Button>
          <Button
            variant="outline"
            onClick={() => draftReport.mutate()}
            disabled={draftReport.isPending}
          >
            {draftReport.isPending ? "Drafting…" : "Generate Report"}
          </Button>
          <Button onClick={handleExport}>Download Test Cases (.xlsx)</Button>
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
              onToggleInclude={(id, included) => toggleInclude.mutate({ id, included })}
              onDelete={(id) => deleteCase.mutate(id)}
              onPatch={(id, patch) => patchCase.mutate({ id, patch })}
              onDraftBug={(id) => draftBug.mutate(id)}
              selectedForRun={selectedForRun.has(c.id)}
              onToggleForRun={toggleForRun}
            />
          ))}
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Generate functional test cases</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <Label>Stories to generate from</Label>
            <div className="mt-2 flex flex-col gap-1">
              {stories?.length === 0 && (
                <p className="text-muted-foreground text-sm">
                  No stories on this project yet — go back to the project page to add one.
                </p>
              )}
              {stories?.map((s) => (
                <label key={s.id} className="flex items-center gap-2 text-sm">
                  <Checkbox
                    checked={selectedStoryIds.includes(s.id)}
                    onChange={(e) =>
                      setSelectedStoryIds((prev) =>
                        e.target.checked ? [...prev, s.id] : prev.filter((id) => id !== s.id),
                      )
                    }
                  />
                  {s.title}
                </label>
              ))}
            </div>
            <Button
              variant="outline"
              size="sm"
              className="mt-2"
              onClick={() => setShowPaste((v) => !v)}
            >
              {showPaste ? "Cancel" : "Paste a new story"}
            </Button>
          </div>

          {showPaste && (
            <form
              onSubmit={handlePasteSubmit((values) => pasteStory.mutate(values))}
              className="flex flex-col gap-3 rounded-md border p-4"
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="paste-title">Title</Label>
                <Input
                  id="paste-title"
                  {...registerPaste("title")}
                  aria-invalid={!!pasteErrors.title}
                />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="paste-text">Story text</Label>
                <Textarea
                  id="paste-text"
                  rows={6}
                  {...registerPaste("text")}
                  aria-invalid={!!pasteErrors.text}
                />
              </div>
              <Button type="submit" disabled={isPasting} className="self-start">
                {isPasting ? "Saving…" : "Save story"}
              </Button>
            </form>
          )}

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
            <div className="flex flex-col gap-2">
              <Label htmlFor="coverage">Coverage depth</Label>
              <Select
                id="coverage"
                value={coverageDepth}
                onChange={(e) =>
                  setCoverageDepth(e.target.value as (typeof COVERAGE_DEPTHS)[number])
                }
              >
                {COVERAGE_DEPTHS.map((d) => (
                  <option key={d} value={d}>
                    {d}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="context">Additional context (optional)</Label>
              <Input
                id="context"
                value={additionalContext}
                onChange={(e) => setAdditionalContext(e.target.value)}
              />
            </div>
          </div>

          <Button
            onClick={() => startGeneration.mutate()}
            disabled={selectedStoryIds.length === 0 || isGenerating}
            className="self-start"
          >
            {isGenerating ? "Generating…" : "Generate Functional Test Cases"}
          </Button>

          {progressLines.length > 0 && (
            <div className="bg-muted rounded-md p-3 text-sm">
              {progressLines.map((line, i) => (
                <div key={i}>{line}</div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      {functional.length > 0 && (
        <div>
          <h2 className="mb-2 text-lg font-semibold">Functional scenarios ({functional.length})</h2>
          <div className="flex flex-col gap-3">
            {functional.map((c) => (
              <CaseCard
                key={c.id}
                c={c}
                onToggleInclude={(id, included) => toggleInclude.mutate({ id, included })}
                onDelete={(id) => deleteCase.mutate(id)}
                onPatch={(id, patch) => patchCase.mutate({ id, patch })}
                onDraftBug={(id) => draftBug.mutate(id)}
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

      <BugsPanel suiteId={suiteId} />
    </div>
  );
}
