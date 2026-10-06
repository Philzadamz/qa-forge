"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { apiFetch } from "@/lib/api";
import type { AuditLogEntry } from "@/lib/types/audit";

const PAGE_SIZE = 50;

export default function AuditLogPage() {
  const [action, setAction] = useState("");
  const [entity, setEntity] = useState("");
  const [offset, setOffset] = useState(0);

  const params = new URLSearchParams({ limit: String(PAGE_SIZE), offset: String(offset) });
  if (action) params.set("action", action);
  if (entity) params.set("entity", entity);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["admin", "audit-log", action, entity, offset],
    queryFn: () => apiFetch<AuditLogEntry[]>(`/admin/audit-log?${params.toString()}`),
  });

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Audit log</h1>
        <p className="text-muted-foreground text-sm">
          Every create, update, delete, login, password reset, and download, newest first.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-2">
          <Label htmlFor="audit-action">Action</Label>
          <Input
            id="audit-action"
            placeholder="e.g. login"
            value={action}
            onChange={(e) => {
              setAction(e.target.value.trim());
              setOffset(0);
            }}
            className="w-48"
          />
        </div>
        <div className="flex flex-col gap-2">
          <Label htmlFor="audit-entity">Entity</Label>
          <Input
            id="audit-entity"
            placeholder="e.g. project"
            value={entity}
            onChange={(e) => {
              setEntity(e.target.value.trim());
              setOffset(0);
            }}
            className="w-48"
          />
        </div>
      </div>

      {isLoading && <p className="text-muted-foreground text-sm">Loading…</p>}
      {isError && <p className="text-destructive text-sm">Could not load the audit log.</p>}

      <Card>
        <CardContent className="overflow-x-auto py-4">
          <table className="w-full text-sm">
            <thead className="text-muted-foreground text-left">
              <tr>
                <th className="pb-2 font-medium">When</th>
                <th className="pb-2 font-medium">Action</th>
                <th className="pb-2 font-medium">Entity</th>
                <th className="pb-2 font-medium">Entity ID</th>
                <th className="pb-2 font-medium">Actor</th>
                <th className="pb-2 font-medium">IP</th>
              </tr>
            </thead>
            <tbody>
              {data?.map((row) => (
                <tr key={row.id} className="border-t align-top">
                  <td className="py-2 whitespace-nowrap">{new Date(row.at).toLocaleString()}</td>
                  <td className="py-2">{row.action}</td>
                  <td className="py-2">{row.entity}</td>
                  <td className="py-2 font-mono text-xs break-all">{row.entity_id ?? "—"}</td>
                  <td className="py-2 font-mono text-xs break-all">{row.actor_id ?? "system"}</td>
                  <td className="py-2">{row.ip ?? "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data?.length === 0 && (
            <p className="text-muted-foreground py-4 text-sm">No matching entries.</p>
          )}
        </CardContent>
      </Card>

      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={!data || data.length < PAGE_SIZE}
          onClick={() => setOffset(offset + PAGE_SIZE)}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
