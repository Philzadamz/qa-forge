"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRef, useState } from "react";
import { useForm } from "react-hook-form";

import { BackButton } from "@/components/back-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, apiFetch } from "@/lib/api";
import { pasteStorySchema, type PasteStoryInput } from "@/lib/schemas/workspace";
import type { Project, Story, Suite } from "@/lib/types/workspace";

import { ApkPanel } from "./apk-panel";
import { SecretsPanel } from "./secrets-panel";

export function ProjectDetailClient({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [showPaste, setShowPaste] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const { data: project } = useQuery({
    queryKey: ["projects", projectId],
    queryFn: () => apiFetch<Project>(`/projects/${projectId}`),
  });
  const { data: stories } = useQuery({
    queryKey: ["projects", projectId, "stories"],
    queryFn: () => apiFetch<Story[]>(`/projects/${projectId}/stories`),
  });
  const { data: suites } = useQuery({
    queryKey: ["projects", projectId, "suites"],
    queryFn: () => apiFetch<Suite[]>(`/projects/${projectId}/suites`),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<PasteStoryInput>({ resolver: zodResolver(pasteStorySchema) });

  const pasteStory = useMutation({
    mutationFn: (values: PasteStoryInput) =>
      apiFetch<Story>(`/projects/${projectId}/stories/paste`, {
        method: "POST",
        body: JSON.stringify(values),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "stories"] });
      reset();
      setShowPaste(false);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not save the story.")),
  });

  async function handleUpload(file: File) {
    setError(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      await apiFetch(`/projects/${projectId}/stories/upload`, { method: "POST", body: formData });
      queryClient.invalidateQueries({ queryKey: ["projects", projectId, "stories"] });
    } catch (err) {
      setError(describeError(err, "Could not upload that file."));
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  if (!project) return <p className="text-muted-foreground text-sm">Loading…</p>;

  return (
    <div className="flex flex-col gap-6">
      <BackButton fallbackHref="/projects" />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
          <p className="text-muted-foreground text-sm">
            {project.app_code} · prefix {project.id_prefix}
          </p>
        </div>
        <Button asChild>
          <Link href={`/suites/new?project=${project.id}`}>Generate test cases</Link>
        </Button>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>User stories</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              accept=".docx,.pdf,.txt,.md,.xlsx,.csv"
              onChange={(e) => {
                const file = e.target.files?.[0];
                if (file) void handleUpload(file);
              }}
              className="text-sm"
            />
            <Button variant="outline" size="sm" onClick={() => setShowPaste((v) => !v)}>
              {showPaste ? "Cancel" : "Paste text instead"}
            </Button>
          </div>

          {showPaste && (
            <form
              onSubmit={handleSubmit((values) => pasteStory.mutate(values))}
              className="flex flex-col gap-3 rounded-md border p-4"
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="title">Title</Label>
                <Input id="title" {...register("title")} aria-invalid={!!errors.title} />
                {errors.title && <p className="text-destructive text-sm">{errors.title.message}</p>}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="text">Story text</Label>
                <Textarea id="text" rows={8} {...register("text")} aria-invalid={!!errors.text} />
                {errors.text && <p className="text-destructive text-sm">{errors.text.message}</p>}
              </div>
              <Button type="submit" loading={isSubmitting} className="self-start">
                {isSubmitting ? "Saving…" : "Save story"}
              </Button>
            </form>
          )}

          <div className="flex flex-col gap-2">
            {stories?.length === 0 && (
              <p className="text-muted-foreground text-sm">
                No stories yet — upload a file or paste text above.
              </p>
            )}
            {stories?.map((story) => (
              <div
                key={story.id}
                className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
              >
                <span>{story.title}</span>
                <Badge variant="muted">{story.source}</Badge>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Test suites</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-2">
          {suites?.length === 0 && (
            <p className="text-muted-foreground text-sm">
              No suites yet — click &quot;Generate test cases&quot; above.
            </p>
          )}
          {suites?.map((suite) => (
            <Link key={suite.id} href={`/suites/${suite.id}`}>
              <div className="hover:border-primary flex items-center justify-between rounded-md border px-3 py-2 text-sm transition-colors">
                <span>{suite.name}</span>
                <Badge variant="muted">{suite.status}</Badge>
              </div>
            </Link>
          ))}
        </CardContent>
      </Card>

      <ApkPanel projectId={projectId} />
      <SecretsPanel projectId={projectId} />
    </div>
  );
}

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}
