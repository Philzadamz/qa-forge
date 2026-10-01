"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { API_PREFIX, ApiError } from "@/lib/api";
import type { Apk } from "@/lib/types/workspace";

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}

function formatSize(bytes: number): string {
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function ApkPanel({ projectId }: { projectId: string }) {
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const key = ["projects", projectId, "apks"];

  const { data: apks } = useQuery({
    queryKey: key,
    queryFn: async () => {
      const res = await fetch(`${API_PREFIX}/projects/${projectId}/apks`, {
        credentials: "include",
      });
      if (!res.ok) throw new Error("Could not load APKs");
      return (await res.json()) as Apk[];
    },
  });

  const uploadApk = useMutation({
    mutationFn: async (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch(`${API_PREFIX}/projects/${projectId}/apks`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!res.ok) {
        const problem = await res.json().catch(() => null);
        throw new ApiError(problem ?? { title: "Upload failed", status: res.status });
      }
      return (await res.json()) as Apk;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: key });
      setError(null);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not upload that APK.")),
    onSettled: () => {
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  const deleteApk = useMutation({
    mutationFn: async (id: string) => {
      const res = await fetch(`${API_PREFIX}/apks/${id}`, {
        method: "DELETE",
        credentials: "include",
      });
      if (!res.ok) throw new Error("Could not delete that APK");
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <CardTitle>Android APKs</CardTitle>
        <div className="flex items-center gap-2">
          <input
            ref={fileInputRef}
            type="file"
            accept=".apk"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) uploadApk.mutate(file);
            }}
            className="hidden"
            id="apk-upload-input"
          />
          <Button
            size="sm"
            variant="outline"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadApk.isPending}
          >
            {uploadApk.isPending ? "Uploading…" : "Upload APK"}
          </Button>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        <p className="text-muted-foreground text-sm">
          Uploaded APKs are analyzed automatically (package, launch activity, version) for use in
          Android Test Lab runs.
        </p>
        {error && <p className="text-destructive text-sm">{error}</p>}
        {apks?.length === 0 && (
          <p className="text-muted-foreground text-sm">No APKs uploaded for this project yet.</p>
        )}
        {apks?.map((apk) => (
          <div key={apk.id} className="rounded-md border px-3 py-2 text-sm">
            <div className="flex items-center justify-between gap-4">
              <div className="flex items-center gap-2 font-medium">
                {apk.label || apk.file_name}
                <Badge variant="muted">{formatSize(apk.file_size)}</Badge>
              </div>
              <Button variant="destructive" size="sm" onClick={() => deleteApk.mutate(apk.id)}>
                Delete
              </Button>
            </div>
            <div className="text-muted-foreground mt-1 font-mono text-xs">
              {apk.package_name} · {apk.launch_activity} · v{apk.version_name} ({apk.version_code})
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
