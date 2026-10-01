"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { API_PREFIX, ApiError, apiFetch } from "@/lib/api";
import type { DefaultTestCase, ImportPreview, TestCaseType } from "@/lib/types/admin";

import { DefaultCaseForm, type DefaultCasePayload } from "./default-case-form";

export function TypeDetailClient({ typeId }: { typeId: string }) {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [replaceExisting, setReplaceExisting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const typeKey = ["admin", "types", typeId];
  const defaultsKey = ["admin", "types", typeId, "defaults"];

  const { data: type } = useQuery({
    queryKey: typeKey,
    queryFn: () => apiFetch<TestCaseType>(`/admin/types/${typeId}`),
  });
  const { data: defaults, isLoading } = useQuery({
    queryKey: defaultsKey,
    queryFn: () => apiFetch<DefaultTestCase[]>(`/admin/types/${typeId}/defaults`),
  });

  function invalidateDefaults() {
    queryClient.invalidateQueries({ queryKey: defaultsKey });
  }

  const createDefault = useMutation({
    mutationFn: (payload: DefaultCasePayload) =>
      apiFetch<DefaultTestCase>(`/admin/types/${typeId}/defaults`, {
        method: "POST",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      invalidateDefaults();
      setShowCreate(false);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not create the default case.")),
  });

  const updateDefault = useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: DefaultCasePayload }) =>
      apiFetch<DefaultTestCase>(`/admin/defaults/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      }),
    onSuccess: () => {
      invalidateDefaults();
      setEditingId(null);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not save the default case.")),
  });

  const deleteDefault = useMutation({
    mutationFn: (id: string) => apiFetch<void>(`/admin/defaults/${id}`, { method: "DELETE" }),
    onSuccess: invalidateDefaults,
    onError: (err: unknown) => setError(describeError(err, "Could not delete the default case.")),
  });

  const toggleActive = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      apiFetch<DefaultTestCase>(`/admin/defaults/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active }),
      }),
    onSuccess: invalidateDefaults,
  });

  const reorder = useMutation({
    mutationFn: (orderedIds: string[]) =>
      apiFetch<DefaultTestCase[]>(`/admin/types/${typeId}/defaults/reorder`, {
        method: "POST",
        body: JSON.stringify({ ordered_ids: orderedIds }),
      }),
    onSuccess: invalidateDefaults,
  });

  const duplicateType = useMutation({
    mutationFn: () =>
      apiFetch<TestCaseType>(`/admin/types/${typeId}/duplicate`, { method: "POST" }),
    onSuccess: (clone) => router.push(`/types/${clone.id}`),
    onError: (err: unknown) => setError(describeError(err, "Could not duplicate this type.")),
  });

  const toggleTypeActive = useMutation({
    mutationFn: (is_active: boolean) =>
      apiFetch<TestCaseType>(`/admin/types/${typeId}`, {
        method: "PATCH",
        body: JSON.stringify({ is_active }),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: typeKey }),
  });

  const deleteType = useMutation({
    mutationFn: () => apiFetch<void>(`/admin/types/${typeId}`, { method: "DELETE" }),
    onSuccess: () => router.push("/types"),
    onError: (err: unknown) =>
      setError(describeError(err, "This type still has default cases; deactivate it instead.")),
  });

  async function handleImportFile(file: File) {
    setError(null);
    const formData = new FormData();
    formData.append("file", file);
    try {
      const result = await apiFetch<ImportPreview>(`/admin/types/${typeId}/defaults/import`, {
        method: "POST",
        body: formData,
      });
      setPreview(result);
    } catch (err) {
      setError(describeError(err, "Could not parse that workbook."));
    }
  }

  const confirmImport = useMutation({
    mutationFn: () =>
      apiFetch<DefaultTestCase[]>(`/admin/types/${typeId}/defaults/import/confirm`, {
        method: "POST",
        body: JSON.stringify({ cases: preview?.cases ?? [], replace_existing: replaceExisting }),
      }),
    onSuccess: () => {
      invalidateDefaults();
      setPreview(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
    onError: (err: unknown) => setError(describeError(err, "Could not save the imported cases.")),
  });

  function moveCase(index: number, direction: -1 | 1) {
    if (!defaults) return;
    const target = index + direction;
    if (target < 0 || target >= defaults.length) return;
    const ids = defaults.map((d) => d.id);
    [ids[index], ids[target]] = [ids[target], ids[index]];
    reorder.mutate(ids);
  }

  if (!type) return <p className="text-muted-foreground text-sm">Loading…</p>;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="flex items-center gap-2 text-2xl font-semibold tracking-tight">
            {type.name}
            {!type.is_active && <Badge variant="muted">Inactive</Badge>}
          </h1>
          {type.description && <p className="text-muted-foreground text-sm">{type.description}</p>}
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => toggleTypeActive.mutate(!type.is_active)}>
            {type.is_active ? "Deactivate" : "Activate"}
          </Button>
          <Button variant="outline" onClick={() => duplicateType.mutate()}>
            Duplicate
          </Button>
          <Button
            variant="destructive"
            onClick={() => {
              if (confirm(`Delete "${type.name}"? This only works if it has no default cases.`)) {
                deleteType.mutate();
              }
            }}
          >
            Delete
          </Button>
        </div>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Bulk import (ADM-DC-3)</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <input
            ref={fileInputRef}
            type="file"
            accept=".xlsx"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) void handleImportFile(file);
            }}
            className="text-sm"
          />
          {preview && (
            <div className="flex flex-col gap-3 rounded-md border p-4">
              <p className="text-sm">
                Found <strong>{preview.cases.length}</strong> default scenario
                {preview.cases.length === 1 ? "" : "s"}.
              </p>
              {preview.warnings.length > 0 && (
                <ul className="text-sm text-amber-600">
                  {preview.warnings.map((w, i) => (
                    <li key={i}>
                      {w.row ? `Row ${w.row}: ` : ""}
                      {w.message}
                    </li>
                  ))}
                </ul>
              )}
              <label className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={replaceExisting}
                  onChange={(e) => setReplaceExisting(e.target.checked)}
                />
                Replace this type&apos;s existing default cases
              </label>
              <div className="flex gap-2">
                <Button onClick={() => confirmImport.mutate()} disabled={confirmImport.isPending}>
                  {confirmImport.isPending ? "Saving…" : "Save imported cases"}
                </Button>
                <Button variant="outline" onClick={() => setPreview(null)}>
                  Discard
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Default scenarios</h2>
        <div className="flex gap-2">
          <a
            href={`${API_PREFIX}/admin/types/${typeId}/defaults/export`}
            className="text-primary text-sm underline-offset-4 hover:underline"
          >
            Export CSV
          </a>
          <Button size="sm" onClick={() => setShowCreate((v) => !v)}>
            {showCreate ? "Cancel" : "Add default case"}
          </Button>
        </div>
      </div>

      {showCreate && (
        <Card>
          <CardContent className="pt-6">
            <DefaultCaseForm
              submitLabel="Create default case"
              onSubmit={async (payload) => createDefault.mutateAsync(payload)}
              onCancel={() => setShowCreate(false)}
            />
          </CardContent>
        </Card>
      )}

      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}
      {defaults && defaults.length === 0 && !showCreate && (
        <p className="text-muted-foreground text-sm">
          No default cases yet — add one above or bulk import a template workbook.
        </p>
      )}

      <div className="flex flex-col gap-3">
        {defaults?.map((d, index) =>
          editingId === d.id ? (
            <Card key={d.id}>
              <CardContent className="pt-6">
                <DefaultCaseForm
                  initial={d}
                  submitLabel="Save changes"
                  onSubmit={async (payload) => updateDefault.mutateAsync({ id: d.id, payload })}
                  onCancel={() => setEditingId(null)}
                />
              </CardContent>
            </Card>
          ) : (
            <Card key={d.id} className={d.is_active ? undefined : "opacity-60"}>
              <CardContent className="flex flex-col gap-2 py-4">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="text-muted-foreground text-xs font-medium tracking-wide uppercase">
                      {d.feature} · {d.evidence_group}
                    </div>
                    <div className="font-medium">{d.scenario}</div>
                    <ol className="text-muted-foreground mt-1 list-inside list-decimal text-sm">
                      {d.steps.map((step, i) => (
                        <li key={i}>{step}</li>
                      ))}
                    </ol>
                    <div className="mt-1 text-sm">
                      <span className="text-muted-foreground">Expected: </span>
                      {d.expected_result}
                    </div>
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <div className="flex gap-1">
                      <Button
                        variant="outline"
                        size="icon"
                        aria-label="Move up"
                        disabled={index === 0}
                        onClick={() => moveCase(index, -1)}
                      >
                        ↑
                      </Button>
                      <Button
                        variant="outline"
                        size="icon"
                        aria-label="Move down"
                        disabled={index === defaults.length - 1}
                        onClick={() => moveCase(index, 1)}
                      >
                        ↓
                      </Button>
                    </div>
                    <div className="flex gap-1">
                      <Button variant="outline" size="sm" onClick={() => setEditingId(d.id)}>
                        Edit
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => toggleActive.mutate({ id: d.id, is_active: !d.is_active })}
                      >
                        {d.is_active ? "Deactivate" : "Activate"}
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => {
                          if (confirm(`Delete "${d.scenario}"?`)) deleteDefault.mutate(d.id);
                        }}
                      >
                        Delete
                      </Button>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ),
        )}
      </div>
    </div>
  );
}

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}
