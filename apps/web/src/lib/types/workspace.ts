export interface Project {
  id: string;
  name: string;
  app_code: string;
  id_prefix: string;
  user_group_dept: string | null;
  solution_provider: string | null;
  developers: string[];
  reviewed_by: string | null;
  default_test_url: string | null;
  owner_id: string;
  members: string[];
  approvers: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface Story {
  id: string;
  project_id: string;
  title: string;
  source: "upload" | "paste" | "url";
  acceptance_criteria: Record<string, unknown>[];
  created_at: string;
}

export interface StoryDetail extends Story {
  extracted_text: string;
}

export type SuiteStatus = "draft" | "in_review" | "final";

export interface SuiteHeader {
  project_name_line: string;
  user_group_dept: string;
  solution_provider: string;
  developers: string;
  test_done_by: string;
  test_reviewed_by: string;
  start_date: string;
  end_date: string;
  test_description: string;
  endpoint_url: string;
}

export interface Suite {
  id: string;
  project_id: string;
  type_id: string;
  name: string;
  status: SuiteStatus;
  story_ids: string[];
  header_json: Partial<SuiteHeader>;
  test_cycle: number;
  created_at: string;
  updated_at: string;
}

export type GenerationJobStatus = "queued" | "running" | "succeeded" | "failed";

export interface GenerationJob {
  id: string;
  suite_id: string;
  status: GenerationJobStatus;
  model: string;
  prompt_version: string;
  input_tokens: number;
  output_tokens: number;
  error: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
}

export type TestCaseSection = "default" | "functional";
export type TestCaseSource = "default" | "ai" | "manual" | "run";
export type TestStatusValue =
  "Passed" | "Failed" | "Not Tested" | "Suspended" | "Modification" | "Blocked";

export interface WorkspaceCase {
  id: string;
  suite_id: string;
  section: TestCaseSection;
  case_no: number;
  display_id: string;
  feature: string;
  scenario: string;
  steps: string[];
  expected_result: string;
  actual_result: string;
  status: TestStatusValue;
  is_regression: boolean;
  evidence_group: string;
  priority: "P1" | "P2" | "P3" | "P4";
  technique: string[];
  traces_to: string[];
  source: TestCaseSource;
  included: boolean;
  is_duplicate: boolean;
  execution_mode: "manual" | "automated" | null;
  sort_order: number;
  request_plan: Record<string, unknown> | null;
}

export interface Evidence {
  id: string;
  test_case_id: string;
  kind: "screenshot" | "request_log" | "video" | "file";
  caption: string | null;
  sort_order: number;
  created_at: string;
}

export type BugStatus = "open" | "fixed" | "retested" | "closed";
export type SeverityValue = "Critical" | "High" | "Medium" | "Low";

export interface Bug {
  id: string;
  suite_id: string;
  test_case_id: string | null;
  title: string;
  description: string;
  severity: SeverityValue;
  status: BugStatus;
  external_link: string | null;
  created_at: string;
}

export interface FeatureRow {
  name: string;
  description: string;
  implemented: boolean;
  functional: boolean;
}

export interface ExceptionRow {
  case_id: string;
  status_type: string;
  description: string;
  severity: string;
  risk: string;
}

export interface ApprovalRow {
  action: string;
  name: string;
  staff_id: string;
  signature_key: string | null;
  date: string;
}

export interface ResultAnalysisFields {
  test_cycles: number;
  total: number;
  passed: number;
  failed: number;
  unexecuted: number;
  suspended: number;
  modification: number;
}

export interface BugsSummaryFields {
  raised: number;
  fixed_retested: number;
  open: number;
}

export interface ReportFields {
  product_name: string;
  pr_links: string[];
  version_numbers: string[];
  test_url: string;
  workitem_url: string;
  jira_link: string;
  general_description: string;
  certified: boolean;
  features: FeatureRow[];
  exit_criteria: string[];
  result_analysis: ResultAnalysisFields;
  automation_ratio: string;
  bugs: BugsSummaryFields;
  exceptions: ExceptionRow[];
  comments: string[];
  approvals: ApprovalRow[];
  classification_label: string;
  ra_overridden: boolean;
  ra_override_reason: string | null;
}

export interface Report {
  id: string;
  suite_id: string;
  fields_json: ReportFields;
  version: number;
  created_at: string;
}

export type SecretKind = "password" | "token" | "api_key" | "oauth_client";

export interface Secret {
  id: string;
  project_id: string;
  name: string;
  kind: SecretKind;
  created_at: string;
}

export interface Apk {
  id: string;
  project_id: string;
  file_name: string;
  file_size: number;
  package_name: string;
  launch_activity: string;
  version_name: string;
  version_code: string;
  label: string;
  created_at: string;
}

export type RunStatus = "queued" | "running" | "passed" | "failed" | "error" | "cancelled";
export type RunStepOutcomeValue = "pass" | "fail" | "skip" | "error";

export interface RunCaseResult {
  status: TestStatusValue;
  actual_result: string;
  confidence: number;
  mode: "agent" | "script" | "deterministic" | "api";
  applied: boolean;
}

export interface RunSummary {
  total?: number;
  passed?: number;
  failed?: number;
  blocked?: number;
  cases?: Record<string, RunCaseResult>;
}

export interface Run {
  id: string;
  suite_id: string | null;
  project_id: string;
  target: "web" | "api" | "android";
  status: RunStatus;
  config_json: Record<string, unknown>;
  guidance_text: string;
  selected_case_ids: string[];
  started_at: string | null;
  finished_at: string | null;
  summary_json: RunSummary;
  error: string | null;
  created_at: string;
}

export interface EndpointParam {
  name: string;
  location: "path" | "query" | "header";
  required: boolean;
  schema_type: string;
}

export interface EndpointInfo {
  method: string;
  path: string;
  summary: string;
  parameters: EndpointParam[];
  request_body_schema: Record<string, unknown> | null;
  response_schemas: Record<string, Record<string, unknown>>;
}

export interface EndpointCatalogue {
  base_url: string | null;
  endpoints: EndpointInfo[];
}

export interface RunStep {
  id: string;
  test_case_id: string | null;
  seq: number;
  action: string;
  target: string | null;
  input_masked: string | null;
  assertion: string | null;
  outcome: RunStepOutcomeValue;
  message: string | null;
  screenshot_evidence_id: string | null;
  duration_ms: number | null;
}
