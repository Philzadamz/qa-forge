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
import { apiFetch } from "@/lib/api";
import type { Bug, BugStatus } from "@/lib/types/workspace";

const bugSchema = z.object({
  title: z.string().trim().min(1, "Enter a title"),
  description: z.string().trim().optional(),
  severity: z.enum(["Critical", "High", "Medium", "Low"]),
});
type BugInput = z.infer<typeof bugSchema>;

const STATUS_OPTIONS: BugStatus[] = ["open", "fixed", "retested", "closed"];

export function BugsPanel({ suiteId }: { suiteId: string }) {
  const queryClient = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const key = ["suites", suiteId, "bugs"];

  const { data: bugs } = useQuery({
    queryKey: key,
    queryFn: () => apiFetch<Bug[]>(`/suites/${suiteId}/bugs`),
  });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<BugInput>({
    resolver: zodResolver(bugSchema),
    defaultValues: { severity: "Medium" },
  });

  const createBug = useMutation({
    mutationFn: (values: BugInput) =>
      apiFetch<Bug>(`/suites/${suiteId}/bugs`, { method: "POST", body: JSON.stringify(values) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key });
      reset();
      setShowForm(false);
    },
  });

  const patchStatus = useMutation({
    mutationFn: ({ id, status }: { id: string; status: BugStatus }) =>
      apiFetch<Bug>(`/bugs/${id}`, { method: "PATCH", body: JSON.stringify({ status }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const deleteBug = useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/bugs/${id}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Bugs ({bugs?.length ?? 0})</CardTitle>
        <Button size="sm" variant="outline" onClick={() => setShowForm((v) => !v)}>
          {showForm ? "Cancel" : "New bug"}
        </Button>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {showForm && (
          <form
            onSubmit={handleSubmit((values) => createBug.mutate(values))}
            className="flex flex-col gap-3 rounded-md border p-4"
          >
            <div className="flex flex-col gap-2">
              <Label htmlFor="bug-title">Title</Label>
              <Input id="bug-title" {...register("title")} aria-invalid={!!errors.title} />
              {errors.title && <p className="text-destructive text-sm">{errors.title.message}</p>}
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bug-description">Description</Label>
              <Input id="bug-description" {...register("description")} />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="bug-severity">Severity</Label>
              <Select id="bug-severity" {...register("severity")} className="w-40">
                <option value="Critical">Critical</option>
                <option value="High">High</option>
                <option value="Medium">Medium</option>
                <option value="Low">Low</option>
              </Select>
            </div>
            <Button type="submit" loading={isSubmitting} className="self-start">
              {isSubmitting ? "Saving…" : "Create bug"}
            </Button>
          </form>
        )}

        {bugs?.length === 0 && (
          <p className="text-muted-foreground text-sm">No bugs filed for this suite.</p>
        )}

        {bugs?.map((bug) => (
          <div
            key={bug.id}
            className="flex items-center justify-between gap-4 rounded-md border px-3 py-2"
          >
            <div>
              <div className="flex items-center gap-2 text-sm font-medium">
                {bug.title}
                <Badge
                  variant={
                    bug.severity === "Critical" || bug.severity === "High" ? "destructive" : "muted"
                  }
                >
                  {bug.severity}
                </Badge>
              </div>
              {bug.description && (
                <div className="text-muted-foreground text-sm">{bug.description}</div>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Select
                value={bug.status}
                onChange={(e) =>
                  patchStatus.mutate({ id: bug.id, status: e.target.value as BugStatus })
                }
                className="h-9 w-32"
              >
                {STATUS_OPTIONS.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </Select>
              <Button variant="destructive" size="sm" onClick={() => deleteBug.mutate(bug.id)}>
                Delete
              </Button>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
