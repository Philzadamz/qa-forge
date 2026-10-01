"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { ApiError, apiFetch } from "@/lib/api";
import type { Secret, SecretKind } from "@/lib/types/workspace";

const secretSchema = z.object({
  name: z.string().trim().min(1, "Enter a name"),
  value: z.string().trim().min(1, "Enter a value"),
  kind: z.enum(["password", "token", "api_key", "oauth_client"]),
});
type SecretInput = z.infer<typeof secretSchema>;

const KIND_OPTIONS: SecretKind[] = ["password", "token", "api_key", "oauth_client"];

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}

export function SecretsPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const key = ["projects", projectId, "secrets"];

  const { data: secrets } = useQuery({
    queryKey: key,
    queryFn: () => apiFetch<Secret[]>(`/projects/${projectId}/secrets`),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<SecretInput>({
    resolver: zodResolver(secretSchema),
    defaultValues: { kind: "password" },
  });

  const createSecret = useMutation({
    mutationFn: (values: SecretInput) =>
      apiFetch<Secret>(`/projects/${projectId}/secrets`, {
        method: "POST",
        body: JSON.stringify(values),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key });
      reset();
      setShowForm(false);
      setError(null);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not save the secret.")),
  });

  const deleteSecret = useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/secrets/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Secrets</CardTitle>
        <Button size="sm" variant="outline" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "New secret"}
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <p className="text-muted-foreground text-sm">
          Credentials for Test Lab runs. Values are encrypted and never shown again — reference them
          by name (e.g. <code>demo_password</code>) when the agent needs to fill a field.
        </p>
        {error && <p className="text-destructive text-sm">{error}</p>}

        {showForm && (
          <form
            onSubmit={handleSubmit((values) => createSecret.mutate(values))}
            className="flex flex-col gap-3 rounded-md border p-4"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="secret-name">Name</Label>
              <Input id="secret-name" {...register("name")} aria-invalid={!!errors.name} />
              {errors.name && <p className="text-destructive text-sm">{errors.name.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="secret-value">Value</Label>
              <Input
                id="secret-value"
                type="password"
                {...register("value")}
                aria-invalid={!!errors.value}
              />
              {errors.value && <p className="text-destructive text-sm">{errors.value.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="secret-kind">Kind</Label>
              <Select id="secret-kind" {...register("kind")} className="w-40">
                {KIND_OPTIONS.map((k) => (
                  <option key={k} value={k}>
                    {k}
                  </option>
                ))}
              </Select>
            </div>
            <Button type="submit" disabled={isSubmitting} className="self-start">
              {isSubmitting ? "Saving…" : "Save secret"}
            </Button>
          </form>
        )}

        {secrets?.length === 0 && (
          <p className="text-muted-foreground text-sm">No secrets saved for this project yet.</p>
        )}
        {secrets?.map((s) => (
          <div
            key={s.id}
            className="flex items-center justify-between rounded-md border px-3 py-2 text-sm"
          >
            <div className="flex items-center gap-2">
              <code>{s.name}</code>
              <Badge variant="muted">{s.kind}</Badge>
            </div>
            <Button variant="destructive" size="sm" onClick={() => deleteSecret.mutate(s.id)}>
              Delete
            </Button>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
