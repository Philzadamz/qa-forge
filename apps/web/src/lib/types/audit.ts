export interface AuditLogEntry {
  id: string;
  actor_id: string | null;
  action: string;
  entity: string;
  entity_id: string | null;
  diff: Record<string, unknown>;
  ip: string | null;
  at: string;
}
