"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ApiError, apiFetch } from "@/lib/api";
import { suiteSetupSchema, type SuiteSetupInput } from "@/lib/schemas/workspace";
import type { Project, Suite } from "@/lib/types/workspace";
import type { TestCaseType } from "@/lib/types/admin";

function NewSuiteForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const preselectedProject = searchParams.get("project") ?? "";
  const [projectId, setProjectId] = useState(preselectedProject);
  const [error, setError] = useState<string | null>(null);

  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: () => apiFetch<Project[]>("/projects"),
  });
  const { data: types } = useQuery({
    queryKey: ["types"],
    queryFn: () => apiFetch<TestCaseType[]>("/types"),
  });

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<SuiteSetupInput>({ resolver: zodResolver(suiteSetupSchema) });

  const createSuite = useMutation({
    mutationFn: (values: SuiteSetupInput) => {
      const project = projects?.find((p) => p.id === projectId);
      const projectNameLine = project ? `${project.app_code}: ${values.name}` : values.name;
      return apiFetch<Suite>("/suites", {
        method: "POST",
        body: JSON.stringify({
          project_id: projectId,
          type_id: values.type_id,
          name: values.name,
          header: {
            project_name_line: projectNameLine,
            user_group_dept: values.user_group_dept || project?.user_group_dept || "",
            solution_provider: values.solution_provider || project?.solution_provider || "",
            developers: values.developers || "",
            test_done_by: values.test_done_by || "",
            test_reviewed_by: values.test_reviewed_by || "",
            start_date: values.start_date || "",
            end_date: values.end_date || "",
            test_description: values.test_description || "",
            endpoint_url: values.endpoint_url || project?.default_test_url || "",
          },
        }),
      });
    },
    onSuccess: (suite) => router.push(`/suites/${suite.id}`),
    onError: (err: unknown) =>
      setError(
        err instanceof ApiError
          ? (err.problem.detail ?? err.message)
          : "Could not create the suite.",
      ),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Generate Test Cases</h1>
        <p className="text-muted-foreground text-sm">
          PRD §7.3 — set up the suite, then defaults appear instantly.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Setup</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            onSubmit={handleSubmit((values) => createSuite.mutate(values))}
            className="grid grid-cols-1 gap-4 md:grid-cols-2"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="project">Project</Label>
              <Select id="project" value={projectId} onChange={(e) => setProjectId(e.target.value)}>
                <option value="">Select a project…</option>
                {projects?.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="type_id">Test case type</Label>
              <Select id="type_id" {...register("type_id")} aria-invalid={!!errors.type_id}>
                <option value="">Select a type…</option>
                {types?.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </Select>
              {errors.type_id && (
                <p className="text-destructive text-sm">{errors.type_id.message}</p>
              )}
            </div>
            <div className="flex flex-col gap-2 md:col-span-2">
              <Label htmlFor="name">Suite name</Label>
              <Input id="name" {...register("name")} aria-invalid={!!errors.name} />
              {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="test_done_by">Test done by</Label>
              <Input id="test_done_by" {...register("test_done_by")} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="test_reviewed_by">Test reviewed by</Label>
              <Input id="test_reviewed_by" {...register("test_reviewed_by")} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="start_date">Testing start date</Label>
              <Input id="start_date" placeholder="DD/MM/YYYY" {...register("start_date")} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="end_date">Testing end date</Label>
              <Input id="end_date" placeholder="DD/MM/YYYY" {...register("end_date")} />
            </div>
            <div className="flex flex-col gap-2 md:col-span-2">
              <Label htmlFor="test_description">Test description</Label>
              <Input id="test_description" {...register("test_description")} />
            </div>
            {error && <p className="text-destructive text-sm md:col-span-2">{error}</p>}
            <Button
              type="submit"
              disabled={isSubmitting || !projectId}
              className="self-start md:col-span-2"
            >
              {isSubmitting ? "Creating…" : "Create suite"}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function NewSuitePage() {
  return (
    <Suspense fallback={<p className="text-muted-foreground text-sm">Loading…</p>}>
      <NewSuiteForm />
    </Suspense>
  );
}
