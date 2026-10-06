export interface RecentRun {
  id: string;
  suite_id: string | null;
  suite_name: string | null;
  target: "web" | "api" | "android";
  status: "queued" | "running" | "passed" | "failed" | "error" | "cancelled";
  total: number;
  passed: number;
  failed: number;
  created_at: string;
}

export interface FeatureUsage {
  feature: string;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface UsageSummary {
  window_days: number;
  prompt_tokens: number;
  completion_tokens: number;
  cost_estimate: number;
  by_feature: FeatureUsage[];
}

export interface Dashboard {
  project_count: number;
  suite_count: number;
  run_count_30_days: number;
  pass_rate_30_days: number | null;
  recent_runs: RecentRun[];
  usage: UsageSummary;
}
