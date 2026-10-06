"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { API_PREFIX, ApiError, apiFetch } from "@/lib/api";
import { pasteStorySchema, type PasteStoryInput } from "@/lib/schemas/workspace";
import type { GenerationJob, Story } from "@/lib/types/workspace";

const COVERAGE_DEPTHS = ["Essential", "Standard", "Exhaustive"] as const;

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}

// Owns the generation form's state, so typing here doesn't re-render the suite's case list.
export function GenerationCard({ suiteId, projectId }: { suiteId: string; projectId: string }) {
  const queryClient = useQueryClient();
  const casesKey = ["suites", suiteId, "cases"];
  const [error, setError] = useState<string | null>(null);
  const [selectedStoryIds, setSelectedStoryIds] = useState<string[]>([]);
  const [coverageDepth, setCoverageDepth] = useState<(typeof COVERAGE_DEPTHS)[number]>("Standard");
  const [additionalContext, setAdditionalContext] = useState("");
  const [showPaste, setShowPaste] = useState(false);
  const [progressLines, setProgressLines] = useState<string[]>([]);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const eventSourceRef = useRef<EventSource | null>(null);
  const { data: stories } = useQuery({
    queryKey: ["projects", projectId, "stories"],
    queryFn: () => apiFetch<Story[]>(`/projects/${projectId}/stories`),
    enabled: !!projectId,
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
      apiFetch<Story>(`/projects/${projectId}/stories/paste`, {
        method: "POST",
        body: JSON.stringify(values),
      }),
    onSuccess: (story) => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "stories"] });
      setSelectedStoryIds((prev) => [...prev, story.id]);
      resetPaste();
      setShowPaste(false);
    },
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

  const isGenerating = job?.status === "queued" || job?.status === "running";
  const selectedStories = stories?.filter((s) => selectedStoryIds.includes(s.id)) ?? [];
  // The case list is refreshed from the job's own state, not only from the live event stream,
  // which can drop during a long generation and would otherwise leave new cases unseen.
  useEffect(() => {
    queryClient.invalidateQueries({ queryKey: ["suites", suiteId, "cases"] });
  }, [job, queryClient, suiteId]);

  useEffect(() => {
    if (!isGenerating) return;
    const timer = setInterval(
      () => queryClient.invalidateQueries({ queryKey: ["suites", suiteId, "cases"] }),
      3000,
    );
    return () => clearInterval(timer);
  }, [isGenerating, queryClient, suiteId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Generate functional test cases</CardTitle>
        <CardDescription>
          Pick the stories to cover, choose how deep to go, then generate. Cases appear below as
          each feature finishes.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-6">
        {error && <p className="text-destructive text-sm">{error}</p>}
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
                    active ? "border-primary bg-primary text-primary-foreground" : "hover:bg-muted"
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
  );
}
