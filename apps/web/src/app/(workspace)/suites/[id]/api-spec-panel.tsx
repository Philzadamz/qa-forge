"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { API_PREFIX, ApiError } from "@/lib/api";
import type { EndpointCatalogue, EndpointInfo } from "@/lib/types/workspace";

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}

type SpecKind = "openapi" | "postman" | "curl";

export function ApiSpecPanel({ suiteId }: { suiteId: string }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<SpecKind>("openapi");
  const [url, setUrl] = useState("");
  const [curlText, setCurlText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [catalogue, setCatalogue] = useState<EndpointCatalogue | null>(null);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [guidance, setGuidance] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [generatedCount, setGeneratedCount] = useState<number | null>(null);

  const parseSpec = useMutation({
    mutationFn: async () => {
      const formData = new FormData();
      formData.append("kind", kind);
      if (kind === "openapi" && url) formData.append("url", url);
      if (kind === "postman" && file) formData.append("file", file);
      if (kind === "openapi" && file) formData.append("file", file);
      if (kind === "curl") formData.append("curl_text", curlText);
      const res = await fetch(`${API_PREFIX}/api-specs/parse`, {
        method: "POST",
        body: formData,
        credentials: "include",
      });
      if (!res.ok) {
        const problem = await res.json().catch(() => null);
        throw new ApiError(problem ?? { title: "Parse failed", status: res.status });
      }
      return (await res.json()) as EndpointCatalogue;
    },
    onSuccess: (data) => {
      setCatalogue(data);
      setSelected(new Set(data.endpoints.map((_, i) => i)));
      setError(null);
      setGeneratedCount(null);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not parse that spec.")),
  });

  const generateCases = useMutation({
    mutationFn: async () => {
      const endpoints: EndpointInfo[] = (catalogue?.endpoints ?? []).filter((_, i) =>
        selected.has(i),
      );
      const res = await fetch(`${API_PREFIX}/suites/${suiteId}/generate-api-cases`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        credentials: "include",
        body: JSON.stringify({ suite_id: suiteId, endpoints, guidance }),
      });
      if (!res.ok) {
        const problem = await res.json().catch(() => null);
        throw new ApiError(problem ?? { title: "Generation failed", status: res.status });
      }
      return (await res.json()) as unknown[];
    },
    onSuccess: (cases) => {
      queryClient.invalidateQueries({ queryKey: ["suites", suiteId, "cases"] });
      setGeneratedCount(cases.length);
      setError(null);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not generate API test cases.")),
  });

  return (
    <div className="flex flex-col gap-4 rounded-md border p-4">
      <h3 className="text-sm font-medium">API spec → test cases</h3>
      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-2">
          <Label htmlFor="spec-kind">Source</Label>
          <Select
            id="spec-kind"
            value={kind}
            onChange={(e) => setKind(e.target.value as SpecKind)}
            className="w-36"
          >
            <option value="openapi">OpenAPI</option>
            <option value="postman">Postman</option>
            <option value="curl">cURL</option>
          </Select>
        </div>
        {kind === "openapi" && (
          <div className="flex flex-1 flex-col gap-2">
            <Label htmlFor="spec-url">Spec URL (or choose a file below)</Label>
            <Input
              id="spec-url"
              placeholder="https://api.example.com/openapi.json"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
            />
          </div>
        )}
      </div>

      {(kind === "openapi" || kind === "postman") && (
        <input
          type="file"
          accept={kind === "openapi" ? ".json,.yaml,.yml" : ".json"}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm"
        />
      )}
      {kind === "curl" && (
        <Textarea
          rows={4}
          placeholder={
            'curl -X POST https://api.example.com/transfers -H "Authorization: Bearer x" -d \'{"amount": 100}\''
          }
          value={curlText}
          onChange={(e) => setCurlText(e.target.value)}
        />
      )}

      {error && <p className="text-destructive text-sm">{error}</p>}

      <Button
        variant="outline"
        size="sm"
        className="self-start"
        onClick={() => parseSpec.mutate()}
        disabled={parseSpec.isPending}
      >
        {parseSpec.isPending ? "Parsing…" : "Parse endpoints"}
      </Button>

      {catalogue && (
        <div className="flex flex-col gap-3 border-t pt-3">
          <div className="flex flex-col gap-1">
            {catalogue.endpoints.map((e, i) => (
              <label key={`${e.method}-${e.path}-${i}`} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={selected.has(i)}
                  onChange={(ev) =>
                    setSelected((prev) => {
                      const next = new Set(prev);
                      if (ev.target.checked) next.add(i);
                      else next.delete(i);
                      return next;
                    })
                  }
                />
                <span className="font-mono text-xs">{e.method}</span> {e.path}
                {e.summary && <span className="text-muted-foreground">— {e.summary}</span>}
              </label>
            ))}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="api-guidance">Guidance (optional)</Label>
            <Input
              id="api-guidance"
              value={guidance}
              onChange={(e) => setGuidance(e.target.value)}
              placeholder="Focus on auth and boundary values…"
            />
          </div>
          <Button
            onClick={() => generateCases.mutate()}
            disabled={selected.size === 0 || generateCases.isPending}
            className="self-start"
          >
            {generateCases.isPending
              ? "Generating…"
              : `Generate API Test Cases (${selected.size} endpoint(s))`}
          </Button>
          {generatedCount !== null && (
            <p className="text-sm text-green-700">Generated {generatedCount} test case(s).</p>
          )}
        </div>
      )}
    </div>
  );
}
