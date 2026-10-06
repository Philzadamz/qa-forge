"use client";

import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { API_PREFIX, ApiError, apiFetch } from "@/lib/api";
import type { Report } from "@/lib/types/workspace";

function describeError(err: unknown): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return "Could not save the signature.";
}

export function SignatureField({
  reportId,
  index,
  signatureKey,
  onChanged,
}: {
  reportId: string;
  index: number;
  signatureKey: string | null;
  onChanged: (key: string | null) => void;
}) {
  const [busy, setBusy] = useState<"upload" | "remove" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const base = `/reports/${reportId}/approvals/${index}/signature`;

  async function upload(file: File) {
    setError(null);
    setBusy("upload");
    try {
      const body = new FormData();
      body.append("file", file);
      const updated = await apiFetch<Report>(base, { method: "POST", body });
      onChanged(
        (updated.fields_json.approvals as { signature_key?: string | null }[])[index]
          ?.signature_key ?? null,
      );
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(null);
    }
  }

  async function remove() {
    setError(null);
    setBusy("remove");
    try {
      await apiFetch<Report>(base, { method: "DELETE" });
      onChanged(null);
    } catch (err) {
      setError(describeError(err));
    } finally {
      setBusy(null);
    }
  }

  function onPaste(e: React.ClipboardEvent<HTMLDivElement>) {
    const item = Array.from(e.clipboardData.items).find((i) => i.type.startsWith("image/"));
    const file = item?.getAsFile();
    if (!file) return;
    e.preventDefault();
    void upload(file);
  }

  if (signatureKey) {
    return (
      <div className="flex flex-col gap-2">
        {/* Authenticated image from the API; next/image can't fetch it through the session. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={`${API_PREFIX}${base}?k=${encodeURIComponent(signatureKey)}`}
          alt={`Signature for approval ${index + 1}`}
          className="bg-background h-14 w-full rounded-md border object-contain p-1"
        />
        <div className="flex gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fileInput.current?.click()}
            loading={busy === "upload"}
          >
            Replace
          </Button>
          <Button variant="ghost" size="sm" onClick={remove} loading={busy === "remove"}>
            Remove
          </Button>
        </div>
        <input
          ref={fileInput}
          type="file"
          accept="image/png,image/jpeg,image/gif,image/webp"
          className="hidden"
          onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])}
        />
        {error && <p className="text-destructive text-xs">{error}</p>}
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <div
        tabIndex={0}
        onPaste={onPaste}
        aria-label="Paste a signature image here"
        className="text-muted-foreground focus-visible:ring-ring flex h-14 flex-col items-center justify-center rounded-md border border-dashed px-2 text-center text-xs focus-visible:ring-2 focus-visible:outline-none"
      >
        {busy === "upload"
          ? "Saving signature…"
          : "Click here and press ⌘/Ctrl+V to paste an image"}
      </div>
      <Button
        variant="outline"
        size="sm"
        onClick={() => fileInput.current?.click()}
        loading={busy === "upload"}
      >
        Upload image
      </Button>
      <input
        ref={fileInput}
        type="file"
        accept="image/png,image/jpeg,image/gif,image/webp"
        className="hidden"
        onChange={(e) => e.target.files?.[0] && void upload(e.target.files[0])}
      />
      {error && <p className="text-destructive text-xs">{error}</p>}
    </div>
  );
}
