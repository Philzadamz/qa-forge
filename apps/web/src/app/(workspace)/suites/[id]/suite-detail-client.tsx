"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { BackButton } from "@/components/back-button";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { API_PREFIX, ApiError, apiFetch, apiFetchBlob } from "@/lib/api";
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
  const isGenerating = job?.status === "queued" || job?.status === "running";
  const selectedStories = stories?.filter((s) => selectedStoryIds.includes(s.id)) ?? [];

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
          <Button
            variant="outline"
            onClick={() => draftReport.mutate()}
            loading={draftReport.isPending}
          >
            {draftReport.isPending ? "Generating report…" : "Generate Report"}
          </Button>
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
          <CardDescription>
            Pick the stories to cover, choose how deep to go, then generate. Cases appear below as
            each feature finishes.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-6">
          <section className="flex flex-col gap-3" aria-labelledby="gen-stories">
            <div className="flex items-center justify-between gap-3">
              <h3 id="gen-stories" className="text-sm font-semibold">
                1. Stories
              </h3>
              <Button variant="outline" size="sm" onClick={() => setShowPaste((v) => !v)}>
                {showPaste ? "Cancel" : "Paste a new story"}
              </Button>
            </div>

            {stories?.length === 0 && !showPaste && (
              <div className="text-muted-foreground rounded-md border border-dashed p-6 text-center text-sm">
                This project has no stories yet. Paste one above to get started.
              </div>
            )}

            {stories && stories.length > 0 && (
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {stories.map((story) => {
                  const checked = selectedStoryIds.includes(story.id);
                  return (
                    <label
                      key={story.id}
                      className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
                        checked ? "border-primary bg-primary/5" : "hover:bg-muted/60"
                      }`}
                    >
                      <Checkbox
                        className="mt-0.5 h-5 w-5"
                        checked={checked}
                        onChange={(e) =>
                          setSelectedStoryIds((prev) =>
                            e.target.checked
                              ? [...prev, story.id]
                              : prev.filter((id) => id !== story.id),
                          )
                        }
                      />
                      <span className="flex min-w-0 flex-col">
                        <span className="truncate text-sm font-medium">{story.title}</span>
                        <span className="text-muted-foreground text-xs">
                          {story.source} · {new Date(story.created_at).toLocaleDateString()}
                        </span>
                      </span>
                    </label>
                  );
                })}
              </div>
            )}

            {showPaste && (
              <form
                onSubmit={handlePasteSubmit((values) => pasteStory.mutate(values))}
                className="bg-muted/40 flex flex-col gap-3 rounded-lg border p-4"
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
                <Button type="submit" loading={isPasting} className="self-start">
                  {isPasting ? "Saving story…" : "Save story"}
                </Button>
              </form>
            )}
          </section>

          <section className="flex flex-col gap-3" aria-labelledby="gen-settings">
            <h3 id="gen-settings" className="text-sm font-semibold">
              2. Settings
            </h3>
            <div role="radiogroup" aria-label="Coverage depth" className="grid grid-cols-3 gap-2">
              {COVERAGE_DEPTHS.map((d) => {
                const active = coverageDepth === d;
                return (
                  <button
                    key={d}
                    type="button"
                    role="radio"
                    aria-checked={active}
                    onClick={() => setCoverageDepth(d)}
                    className={`rounded-lg border px-3 py-2 text-sm font-medium transition-colors ${
                      active
                        ? "border-primary bg-primary text-primary-foreground"
                        : "hover:bg-muted"
                    }`}
                  >
                    {d}
                  </button>
                );
              })}
            </div>
            <p className="text-muted-foreground text-xs">
              {coverageDepth === "Essential" && "Core happy paths and the most important failures."}
              {coverageDepth === "Standard" &&
                "Happy paths, validation, and the common failure modes."}
              {coverageDepth === "Exhaustive" &&
                "Edge cases, boundaries, and every failure mode the story implies."}
            </p>
            <div className="flex flex-col gap-2">
              <Label htmlFor="context">Additional context (optional)</Label>
              <Input
                id="context"
                placeholder="e.g. Focus on the mobile app; the OTP step is out of scope"
                value={additionalContext}
                onChange={(e) => setAdditionalContext(e.target.value)}
              />
            </div>
          </section>

          <section className="flex flex-col gap-3" aria-labelledby="gen-run">
            <h3 id="gen-run" className="text-sm font-semibold">
              3. Generate
            </h3>
            <div className="flex flex-wrap items-center gap-3">
              <Button
                onClick={() => startGeneration.mutate()}
                loading={startGeneration.isPending || isGenerating}
                disabled={selectedStoryIds.length === 0}
              >
                {isGenerating
                  ? "Generating…"
                  : `Generate from ${selectedStoryIds.length || "selected"} ${
                      selectedStoryIds.length === 1 ? "story" : "stories"
                    }`}
              </Button>
              {selectedStories.length > 0 && (
                <span className="text-muted-foreground text-xs">
                  {selectedStories.map((s) => s.title).join(" · ")}
                </span>
              )}
            </div>

            {progressLines.length > 0 && (
              <ol className="bg-muted/40 flex flex-col gap-2 rounded-lg border p-4 text-sm">
                {progressLines.map((line, i) => (
                  <li key={i} className="flex items-start gap-2">
                    <span
                      aria-hidden="true"
                      className={`mt-1 inline-block h-2 w-2 shrink-0 rounded-full ${
                        line.startsWith("Failed")
                          ? "bg-destructive"
                          : line === "Done."
                            ? "bg-emerald-500"
                            : "bg-primary"
                      }`}
                    />
                    {line}
                  </li>
                ))}
              </ol>
            )}
          </section>
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
