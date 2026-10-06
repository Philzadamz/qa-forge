"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch } from "@/lib/api";
import { projectSchema, type ProjectInput } from "@/lib/schemas/workspace";
import type { Project } from "@/lib/types/workspace";

export default function ProjectsPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data: projects, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<Project[]>("/projects"),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ProjectInput>({ resolver: zodResolver(projectSchema) });

  const createProject = useMutation({
    mutationFn: (values: ProjectInput) =>
      apiFetch<Project>("/projects", { method: "POST", body: JSON.stringify(values) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["projects"] });
      reset();
      setShowForm(false);
      setError(null);
    },
    onError: (err: unknown) =>
      setError(
        err instanceof ApiError
          ? (err.problem.detail ?? err.message)
          : "Could not create the project.",
      ),
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
          <p className="text-muted-foreground text-sm">
            PRD §7.2 — each project pre-fills its suites&apos; headers.
          </p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "New project"}
        </Button>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>New project</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={handleSubmit((values) => createProject.mutate(values))}
              className="grid grid-cols-1 gap-4 md:grid-cols-2"
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" {...register("name")} aria-invalid={!!errors.name} />
                {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="app_code">App code</Label>
                <Input
                  id="app_code"
                  placeholder="e.g. KUSALA"
                  {...register("app_code")}
                  aria-invalid={!!errors.app_code}
                />
                {errors.app_code && (
                  <p className="text-destructive text-sm">{errors.app_code.message}</p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="id_prefix">Test case ID prefix</Label>
                <Input
                  id="id_prefix"
                  placeholder="e.g. Kusala"
                  {...register("id_prefix")}
                  aria-invalid={!!errors.id_prefix}
                />
                {errors.id_prefix && (
                  <p className="text-destructive text-sm">{errors.id_prefix.message}</p>
                )}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="user_group_dept">User group / dept.</Label>
                <Input id="user_group_dept" {...register("user_group_dept")} />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="solution_provider">Solution provider</Label>
                <Input id="solution_provider" {...register("solution_provider")} />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="default_test_url">Default test URL</Label>
                <Input id="default_test_url" {...register("default_test_url")} />
              </div>
              <Button type="submit" loading={isSubmitting} className="self-start md:col-span-2">
                {isSubmitting ? "Creating…" : "Create project"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}
      {projects && projects.length === 0 && (
        <p className="text-muted-foreground text-sm">
          No projects yet — create one to get started.
        </p>
      )}

      <div className="flex flex-col gap-2">
        {projects?.map((project) => (
          <Link key={project.id} href={`/projects/${project.id}`}>
            <Card className="hover:border-primary transition-colors">
              <CardContent className="py-4">
                <div className="font-medium">{project.name}</div>
                <div className="text-muted-foreground text-sm">
                  {project.app_code} · prefix {project.id_prefix}
                </div>
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
