"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError, apiFetch } from "@/lib/api";
import { testCaseTypeSchema, type TestCaseTypeInput } from "@/lib/schemas/admin";
import type { TestCaseType } from "@/lib/types/admin";

export default function TypesPage() {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const { data: types, isLoading } = useQuery({
    queryKey: ["admin", "types"],
    queryFn: () => apiFetch<TestCaseType[]>("/admin/types"),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TestCaseTypeInput>({ resolver: zodResolver(testCaseTypeSchema) });

  const createType = useMutation({
    mutationFn: (values: TestCaseTypeInput) =>
      apiFetch<TestCaseType>("/admin/types", { method: "POST", body: JSON.stringify(values) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin", "types"] });
      reset();
      setShowForm(false);
      setFormError(null);
    },
    onError: (err: unknown) => {
      setFormError(
        err instanceof ApiError
          ? (err.problem.detail ?? err.message)
          : "Could not create the type.",
      );
    },
  });

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Test Case Types</h1>
          <p className="text-muted-foreground text-sm">
            Each type has its own library of default scenarios (PRD §6.1–6.2).
          </p>
        </div>
        <Button onClick={() => setShowForm((v) => !v)}>{showForm ? "Cancel" : "New type"}</Button>
      </div>

      {showForm && (
        <Card>
          <CardHeader>
            <CardTitle>New test case type</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              onSubmit={handleSubmit((values) => createType.mutate(values))}
              className="flex flex-col gap-4"
            >
              <div className="flex flex-col gap-2">
                <Label htmlFor="name">Name</Label>
                <Input id="name" {...register("name")} aria-invalid={!!errors.name} />
                {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="description">Description</Label>
                <Input id="description" {...register("description")} />
              </div>
              <div className="flex flex-col gap-2">
                <Label htmlFor="id_prefix_hint">ID prefix hint</Label>
                <Input
                  id="id_prefix_hint"
                  placeholder="e.g. Kusala"
                  {...register("id_prefix_hint")}
                />
              </div>
              {formError && <p className="text-destructive text-sm">{formError}</p>}
              <Button type="submit" loading={isSubmitting} className="self-start">
                {isSubmitting ? "Creating…" : "Create type"}
              </Button>
            </form>
          </CardContent>
        </Card>
      )}

      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}

      {types && types.length === 0 && (
        <p className="text-muted-foreground text-sm">
          No test case types yet. Create one to start building a default-scenario library.
        </p>
      )}

      <div className="flex flex-col gap-2">
        {types?.map((type) => (
          <Link key={type.id} href={`/types/${type.id}`}>
            <Card className="hover:border-primary transition-colors">
              <CardContent className="flex items-center justify-between py-4">
                <div>
                  <div className="font-medium">{type.name}</div>
                  {type.description && (
                    <div className="text-muted-foreground text-sm">{type.description}</div>
                  )}
                </div>
                {!type.is_active && <Badge variant="muted">Inactive</Badge>}
              </CardContent>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}
