"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { BackButton } from "@/components/back-button";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { API_PREFIX, ApiError, apiFetch } from "@/lib/api";
import type { Report, ReportFields } from "@/lib/types/workspace";

import { SignatureField } from "./signature-field";

function describeError(err: unknown, fallback: string): string {
  if (err instanceof ApiError) return err.problem.detail ?? err.message;
  return fallback;
}

const linesToList = (text: string): string[] =>
  text
    .split("\n")
    .map((l) => l.trim())
    .filter(Boolean);
const listToLines = (list: string[]): string => list.join("\n");

export function ReportDetailClient({ reportId }: { reportId: string }) {
  const queryClient = useQueryClient();
  const [fields, setFields] = useState<ReportFields | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const { data: report } = useQuery({
    queryKey: ["reports", reportId],
    queryFn: () => apiFetch<Report>(`/reports/${reportId}`),
  });

  useEffect(() => {
    if (report && !fields) setFields(report.fields_json);
  }, [report, fields]);

  const save = useMutation({
    mutationFn: (next: ReportFields) =>
      apiFetch<Report>(`/reports/${reportId}`, {
        method: "PUT",
        body: JSON.stringify({ fields_json: next }),
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["reports", reportId], updated);
      setSavedAt(Date.now());
      setError(null);
    },
    onError: (err: unknown) => setError(describeError(err, "Could not save the report.")),
  });

  async function handleDownload() {
    if (!fields) return;
    setError(null);
    try {
      await save.mutateAsync(fields);
      const res = await fetch(`${API_PREFIX}/reports/${reportId}/render`, {
        method: "POST",
        credentials: "include",
      });
      if (!res.ok) {
        const problem = await res.json().catch(() => null);
        throw new Error(problem?.detail ?? "Render failed");
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${fields.product_name || "report"}_QA_Test_Report.docx`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      setError(describeError(err, "Could not render the report."));
    }
  }

  if (!fields) return <p className="text-muted-foreground text-sm">Loading…</p>;

  function update<K extends keyof ReportFields>(key: K, value: ReportFields[K]) {
    setFields((prev) => (prev ? { ...prev, [key]: value } : prev));
  }

  return (
    <div className="flex flex-col gap-6">
      <BackButton
        fallbackHref={report ? `/suites/${report.suite_id}` : "/dashboard"}
        label="Back to suite"
      />
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">QA Test Completion Report</h1>
          <p className="text-muted-foreground text-sm">
            Version {report?.version} {savedAt && <span>· Saved</span>}
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={() => save.mutate(fields)} loading={save.isPending}>
            {save.isPending ? "Saving…" : "Save draft"}
          </Button>
          <Button onClick={handleDownload}>Download .docx</Button>
        </div>
      </div>

      {error && <p className="text-destructive text-sm">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle>Project info</CardTitle>
        </CardHeader>
        <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="flex flex-col gap-2">
            <Label htmlFor="product_name">Product name</Label>
            <Input
              id="product_name"
              value={fields.product_name}
              onChange={(e) => update("product_name", e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="test_url">Test URL</Label>
            <Input
              id="test_url"
              value={fields.test_url}
              onChange={(e) => update("test_url", e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="pr_links">Pre-master PR link(s)</Label>
            <Textarea
              id="pr_links"
              rows={2}
              value={listToLines(fields.pr_links)}
              onChange={(e) => update("pr_links", linesToList(e.target.value))}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="version_numbers">Version number(s)</Label>
            <Textarea
              id="version_numbers"
              rows={2}
              value={listToLines(fields.version_numbers)}
              onChange={(e) => update("version_numbers", linesToList(e.target.value))}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="workitem_url">Workitem/Repo URL</Label>
            <Input
              id="workitem_url"
              value={fields.workitem_url}
              onChange={(e) => update("workitem_url", e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="jira_link">Jira link</Label>
            <Input
              id="jira_link"
              value={fields.jira_link}
              onChange={(e) => update("jira_link", e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-2 md:col-span-2">
            <Label htmlFor="general_description">General description</Label>
            <Textarea
              id="general_description"
              rows={2}
              value={fields.general_description}
              onChange={(e) => update("general_description", e.target.value)}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Certificate summary</CardTitle>
        </CardHeader>
        <CardContent>
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={fields.certified}
              onChange={(e) => update("certified", e.target.checked)}
            />
            Is this build certified for deployment?
          </label>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Feature status</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {fields.features.map((f, i) => (
            <div key={`${f.name}-${i}`} className="rounded-md border p-3">
              <div className="flex items-center justify-between gap-2">
                <div className="font-medium">{f.name}</div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-destructive hover:text-destructive"
                  aria-label={`Remove feature ${f.name}`}
                  onClick={() =>
                    update(
                      "features",
                      fields.features.filter((_, j) => j !== i),
                    )
                  }
                >
                  Remove
                </Button>
              </div>
              <Textarea
                rows={2}
                className="mt-1"
                value={f.description}
                onChange={(e) => {
                  const next = [...fields.features];
                  next[i] = { ...f, description: e.target.value };
                  update("features", next);
                }}
              />
              <div className="mt-2 flex gap-4 text-sm">
                <label className="flex items-center gap-2">
                  <Checkbox
                    checked={f.implemented}
                    onChange={(e) => {
                      const next = [...fields.features];
                      next[i] = { ...f, implemented: e.target.checked };
                      update("features", next);
                    }}
                  />
                  Implemented
                </label>
                <label className="flex items-center gap-2">
                  <Checkbox
                    checked={f.functional}
                    onChange={(e) => {
                      const next = [...fields.features];
                      next[i] = { ...f, functional: e.target.checked };
                      update("features", next);
                    }}
                  />
                  Functional
                </label>
              </div>
            </div>
          ))}
          {fields.features.length === 0 && (
            <p className="text-muted-foreground text-sm">
              No functional features in this suite yet.
            </p>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Exit criteria</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            rows={3}
            value={listToLines(fields.exit_criteria)}
            onChange={(e) => update("exit_criteria", linesToList(e.target.value))}
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Result analysis</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid grid-cols-3 gap-3 text-sm md:grid-cols-6">
            {(
              [
                ["Cycles", "test_cycles"],
                ["Total", "total"],
                ["Passed", "passed"],
                ["Failed", "failed"],
                ["Un-executed", "unexecuted"],
                ["Suspended", "suspended"],
              ] as const
            ).map(([label, key]) => (
              <div key={key} className="flex flex-col gap-1 rounded-md border p-2">
                <Label htmlFor={`ra-${key}`} className="text-muted-foreground text-xs font-normal">
                  {label}
                </Label>
                <Input
                  id={`ra-${key}`}
                  type="number"
                  min={0}
                  inputMode="numeric"
                  className="h-8 text-center text-base font-semibold"
                  value={fields.result_analysis[key]}
                  onChange={(e) => {
                    update("result_analysis", {
                      ...fields.result_analysis,
                      [key]: Math.max(0, Number(e.target.value) || 0),
                    });
                    update("ra_overridden", true);
                  }}
                />
              </div>
            ))}
          </div>
          <div className="text-sm">
            Automation-to-manual ratio:{" "}
            <span className="font-medium">{fields.automation_ratio}</span>
          </div>
          <div className="grid grid-cols-3 gap-3 text-sm">
            {(
              [
                ["Bugs raised", "raised"],
                ["Fixed & retested", "fixed_retested"],
                ["Open", "open"],
              ] as const
            ).map(([label, key]) => (
              <div key={key} className="flex flex-col gap-1 rounded-md border p-2">
                <Label htmlFor={`bug-${key}`} className="text-muted-foreground text-xs font-normal">
                  {label}
                </Label>
                <Input
                  id={`bug-${key}`}
                  type="number"
                  min={0}
                  inputMode="numeric"
                  className="h-8 text-center text-base font-semibold"
                  value={fields.bugs[key]}
                  onChange={(e) =>
                    update("bugs", {
                      ...fields.bugs,
                      [key]: Math.max(0, Number(e.target.value) || 0),
                    })
                  }
                />
              </div>
            ))}
          </div>
          {!fields.ra_overridden && (
            <p className="text-muted-foreground text-xs">
              These numbers are computed from the suite&apos;s current results. Editing any of them
              marks the report as overridden, and the reason below is then required.
            </p>
          )}
          <label className="flex items-center gap-2 text-sm">
            <Checkbox
              checked={fields.ra_overridden}
              onChange={(e) => update("ra_overridden", e.target.checked)}
            />
            Override — use these numbers as saved, even if the suite has changed
          </label>
          {fields.ra_overridden && (
            <Input
              placeholder="Reason for changing these numbers (required)"
              value={fields.ra_override_reason ?? ""}
              onChange={(e) => update("ra_override_reason", e.target.value)}
            />
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Exceptions &amp; observations ({fields.exceptions.length})</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {fields.exceptions.length === 0 && <p className="text-muted-foreground text-sm">N/A</p>}
          {fields.exceptions.map((ex, i) => (
            <div key={`${ex.case_id}-${i}`} className="rounded-md border p-3 text-sm">
              <div className="flex items-center gap-2 font-medium">
                {ex.case_id}
                <Badge variant="destructive">{ex.status_type}</Badge>
                <Badge variant="muted">{ex.severity}</Badge>
              </div>
              <Textarea
                rows={2}
                className="mt-1"
                value={ex.description}
                onChange={(e) => {
                  const next = [...fields.exceptions];
                  next[i] = { ...ex, description: e.target.value };
                  update("exceptions", next);
                }}
              />
              <Input
                className="mt-1"
                placeholder="Risk assessment"
                value={ex.risk}
                onChange={(e) => {
                  const next = [...fields.exceptions];
                  next[i] = { ...ex, risk: e.target.value };
                  update("exceptions", next);
                }}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Comments / observation</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            rows={6}
            value={fields.comments.join("\n\n")}
            onChange={(e) =>
              update(
                "comments",
                e.target.value
                  .split(/\n\s*\n/)
                  .map((p) => p.trim())
                  .filter(Boolean),
              )
            }
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Reviews and approvals</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {fields.approvals.map((a, i) => (
            <div
              key={a.action}
              className="grid grid-cols-1 items-start gap-3 rounded-md border p-3 md:grid-cols-[1fr_1fr_1fr_1.2fr]"
            >
              <div className="text-sm font-medium md:col-span-4">{a.action}</div>
              <Input
                placeholder="Name"
                aria-label={`${a.action} name`}
                value={a.name}
                onChange={(e) => {
                  const next = [...fields.approvals];
                  next[i] = { ...a, name: e.target.value };
                  update("approvals", next);
                }}
              />
              <Input
                placeholder="Staff ID"
                aria-label={`${a.action} staff ID`}
                value={a.staff_id}
                onChange={(e) => {
                  const next = [...fields.approvals];
                  next[i] = { ...a, staff_id: e.target.value };
                  update("approvals", next);
                }}
              />
              <Input
                placeholder="DD/MM/YYYY"
                aria-label={`${a.action} date`}
                value={a.date}
                onChange={(e) => {
                  const next = [...fields.approvals];
                  next[i] = { ...a, date: e.target.value };
                  update("approvals", next);
                }}
              />
              <SignatureField
                reportId={reportId}
                index={i}
                signatureKey={a.signature_key}
                onChanged={(key) => {
                  const next = [...fields.approvals];
                  next[i] = { ...a, signature_key: key };
                  update("approvals", next);
                }}
              />
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Classification</CardTitle>
        </CardHeader>
        <CardContent>
          <Input
            value={fields.classification_label}
            onChange={(e) => update("classification_label", e.target.value)}
            className="w-48"
          />
        </CardContent>
      </Card>
    </div>
  );
}
