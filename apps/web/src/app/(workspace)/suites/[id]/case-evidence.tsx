"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef } from "react";

import { Button } from "@/components/ui/button";
import { API_PREFIX, apiFetch } from "@/lib/api";
import type { Evidence } from "@/lib/types/workspace";

async function uploadEvidence(caseId: string, file: File): Promise<Evidence> {
  const formData = new FormData();
  formData.append("file", file);
  return apiFetch<Evidence>(`/cases/${caseId}/evidence`, { method: "POST", body: formData });
}

export function CaseEvidence({ caseId }: { caseId: string }) {
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const key = ["cases", caseId, "evidence"];

  const { data: evidence } = useQuery({
    queryKey: key,
    queryFn: () => apiFetch<Evidence[]>(`/cases/${caseId}/evidence`),
  });

  const upload = useMutation({
    mutationFn: (file: File) => uploadEvidence(caseId, file),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const remove = useMutation({
    mutationFn: (evidenceId: string) =>
      apiFetch<void>(`/evidence/${evidenceId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  function handlePaste(e: React.ClipboardEvent<HTMLDivElement>) {
    const item = Array.from(e.clipboardData.items).find((i) => i.type.startsWith("image/"));
    const file = item?.getAsFile();
    if (file) upload.mutate(file);
  }

  return (
    <div
      className="flex flex-col gap-2"
      onPaste={handlePaste}
      tabIndex={0}
      aria-label="Evidence — click and paste a screenshot, or use the upload button"
    >
      <div className="flex flex-wrap gap-2">
        {evidence?.map((e) => (
          <div key={e.id} className="group relative">
            {/* eslint-disable-next-line @next/next/no-img-element -- internal, non-optimized evidence thumbnail */}
            <img
              src={`${API_PREFIX}/evidence/${e.id}/file`}
              alt={e.caption ?? "Evidence"}
              className="h-16 w-16 rounded border object-cover"
            />
            <button
              type="button"
              onClick={() => remove.mutate(e.id)}
              aria-label="Remove evidence"
              className="bg-destructive absolute -top-1.5 -right-1.5 hidden h-5 w-5 rounded-full text-xs text-white group-hover:block"
            >
              ×
            </button>
          </div>
        ))}
      </div>
      <div className="flex items-center gap-2">
        <input
          ref={inputRef}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          className="hidden"
          onChange={(e) => {
            const file = e.target.files?.[0];
            if (file) upload.mutate(file);
            e.target.value = "";
          }}
        />
        <Button type="button" variant="outline" size="sm" onClick={() => inputRef.current?.click()}>
          Add evidence
        </Button>
        <span className="text-muted-foreground text-xs">or click here and paste (Ctrl+V)</span>
      </div>
    </div>
  );
}
